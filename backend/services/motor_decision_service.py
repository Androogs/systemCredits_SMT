"""
Motor de decisión de crédito (estrategia Prefiltro_Cliente, BRD +
PPT v4). Núcleo PURO: no consulta servicios ni base de datos; recibe
la solicitud y los reportes ya normalizados y devuelve un
ResultadoMotor completo y trazable. La orquestación (buró, base de
datos, auditoría) vive en evaluacion_service.py.

Flujo LINEAL (se evalúan todas las etapas y se acumulan TODAS las
causales que disparen):

    1. Filtros duros: exclusión fallecido (score 3), políticas de la
       solicitud (persona natural, edad, nacionalidad, RUNT), 11
       políticas de buró y mora 30 vigente.
    2. Exclusión de score 0 / 4: sin perfil de score; Estudio (E7) si
       el ingreso SMMLV alcanza Ingreso_E_2 (Ingreso_I_2 si es
       independiente), si no Requiere codeudor (RC3).
    3. Valor Ingreso e Ingreso Final.
    4. Perfil de score y perfil de ingreso.
    5. Matriz de decisión por ocupación.
    6. Capacidad de pago (siempre, para trazabilidad).

Decisión interna = la de mayor prioridad entre las causales
(Rechazo > Requiere codeudor > Estudio > Aprobado). La decisión
PÚBLICA es binaria: Aprobado solo si no hay ninguna causal; cualquier
otro caso es Rechazado con sus causales ordenadas por prioridad. Si el
motor no puede justificar una aprobación y no hay causal explícita
(p. ej. falta el score), se usa R20 "Información insuficiente para
aprobar": nunca se aprueba por omisión.
"""

import time
import uuid
from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal

from backend.models.buro_models import RespuestaHDC, RespuestaValorIngreso
from backend.models.enums import (
    PRIORIDAD_DECISION,
    Causal,
    Decision,
    DecisionFinal,
    Ocupacion,
)
from backend.models.motor_models import PasoTraza, ResultadoMotor, Solicitud
from backend.services.capacidad_pago_service import ResultadoCapacidadPago, calcular_capacidad_pago
from backend.services.motor_exceptions import ValidacionError
from backend.services.motor_parametros import MotorParametros
from backend.services.reglas_filtros_duros import evaluar_exclusion_score, evaluar_filtros_duros
from backend.services.reglas_ingreso import calcular_ingreso_final
from backend.services.reglas_perfil import (
    ResultadoDecision,
    ResultadoPerfilScore,
    asignar_perfil_ingreso,
    asignar_perfil_score,
    decidir_por_ocupacion,
)
from backend.services.valor_ingreso_service import calcular_valor_ingreso
from backend.utils.loggers import get_logger

logger = get_logger("motor_decision.motor")

QUANTO_FACTOR_MILES = Decimal(1000)  # HDC+ reporta Quanto en miles de pesos
_DOS_DECIMALES = Decimal("0.01")
_CUATRO_DECIMALES = Decimal("0.0001")


def _q(valor: Decimal, exp: Decimal = _DOS_DECIMALES) -> Decimal:
    """Redondeo de presentación. Las reglas se evalúan antes, sin redondear."""
    return Decimal(valor).quantize(exp)


def extraer_score(hdc: RespuestaHDC, params: MotorParametros) -> tuple[Decimal | None, str | None]:
    """
    Score del modelo contratado, en el orden de preferencia de
    params.codigos_score. Si no aparece ninguno NO se sustituye por otro
    score del reporte (evita decidir con un modelo equivocado).
    """
    for codigo in params.codigos_score:
        for s in hdc.scores:
            if s.tipo == codigo and s.puntaje is not None:
                return s.puntaje, s.tipo
    return None, None


def ordenar_causales(causales: list[Causal]) -> list[Causal]:
    """Deduplica y ordena por prioridad (estable dentro de cada nivel)."""
    unicas = list(dict.fromkeys(c for c in causales if c))
    return sorted(unicas, key=lambda c: -PRIORIDAD_DECISION[c.tipo])


class MotorDecision:
    """Orquestador puro de las reglas del motor."""

    def __init__(self, smmlv: int, ambiente: str = "demo") -> None:
        if not smmlv or smmlv <= 0:
            raise ValidacionError("SMMLV debe ser mayor que cero (variable SMMLV en .env).")
        self.smmlv = smmlv
        self.ambiente = ambiente

    def evaluar(
        self,
        solicitud: Solicitud,
        hdc: RespuestaHDC,
        valor_ingreso: RespuestaValorIngreso | None,
        parametros: MotorParametros,
        fecha_evaluacion: date | None = None,
        advertencias: list[str] | None = None,
    ) -> ResultadoMotor:
        t_inicio = time.perf_counter()
        fecha = fecha_evaluacion or date.today()
        evaluacion_id = str(uuid.uuid4())
        advertencias = list(advertencias or [])
        traza: list[PasoTraza] = []
        causales: list[Causal] = []
        logger.info("Evaluando | id=%s | ocupacion=%s", evaluacion_id, solicitud.ocupacion.value)

        # --- Score y Quanto ---
        score, score_tipo = extraer_score(hdc, parametros)
        if score is None:
            advertencias.append(
                "HDC+ no trae un score de los modelos configurados "
                f"({', '.join(parametros.codigos_score)}); no se asigna perfil de score."
            )
        quanto_pesos = (hdc.quanto.valor_medio or Decimal(0)) * parametros.quanto_factor if hdc.quanto else Decimal(0)
        exclusion = evaluar_exclusion_score(score, parametros)
        score_es_exclusion = exclusion.es_exclusion or exclusion.fallecido
        score_exclusion_ignorada = exclusion.ignorada

        # --- 1. Filtros duros ---
        filtros = evaluar_filtros_duros(hdc, solicitud, parametros, fecha, exclusion)
        causales += filtros.lista_causales
        traza.append(
            PasoTraza(
                etapa="filtros_duros",
                resultado="Dispara" if filtros.aplica else "Sin causales",
                causales=[c.codigo for c in filtros.lista_causales],
                detalle=filtros.detalles,
            )
        )

        # --- 3. Valor Ingreso e Ingreso Final ---
        val_ingreso = calcular_valor_ingreso(
            valor_ingreso, parametros.max_aportantes, parametros.meses_promedio_valor_ingreso
        )
        ingreso_res = calcular_ingreso_final(solicitud, val_ingreso, quanto_pesos)
        ingreso_final = ingreso_res.ingreso_final
        ingreso_smmlv = ingreso_final / Decimal(self.smmlv)
        if ingreso_res.causal_forzada:
            causales.append(ingreso_res.causal_forzada)
        traza.append(
            PasoTraza(
                etapa="ingreso_final",
                resultado=f"{ingreso_final:.0f} COP ({ingreso_smmlv:.4f} SMMLV) - fuente {ingreso_res.fuente}",
                causales=[ingreso_res.causal_forzada.codigo] if ingreso_res.causal_forzada else [],
                detalle=[ingreso_res.razon, f"Valor Ingreso {val_ingreso:.0f}", f"Quanto medio {quanto_pesos:.0f}"],
            )
        )

        # --- 2. Exclusión de score 0 / 4 ---
        if exclusion.es_exclusion:
            # Score 0 o 4 -> Estudio o Codeudor según el ingreso final en SMMLV
            umbral_exclusion = (
                parametros.ingreso_i_2 if solicitud.ocupacion == Ocupacion.INDEPENDIENTE else parametros.ingreso_e_2
            )
            causal_exclusion = Causal.E7 if ingreso_smmlv >= umbral_exclusion else Causal.RC3
            causales.append(causal_exclusion)  # La salida pública continúa siendo binaria
            traza.append(
                PasoTraza(
                    etapa="exclusion_score",
                    resultado=f"Score {exclusion.codigo_exclusion} es código de exclusión",
                    causales=[causal_exclusion.codigo],
                    detalle=[f"Ingreso {ingreso_smmlv:.4f} SMMLV", f"Umbral {umbral_exclusion} SMMLV"],
                )
            )

        # --- 4. Perfiles ---
        if score_es_exclusion:
            perfil_score_res = ResultadoPerfilScore(razon=f"Score {int(score)} tratado como exclusión")
        elif score_exclusion_ignorada:
            perfil_score_res = ResultadoPerfilScore(razon=f"Score {int(score)} excluido ignorado por parámetro")
        else:
            perfil_score_res = asignar_perfil_score(score, solicitud, parametros)
            if perfil_score_res.causal_forzada:
                causales.append(perfil_score_res.causal_forzada)
        traza.append(
            PasoTraza(
                etapa="perfil_score",
                resultado=perfil_score_res.perfil.value if perfil_score_res.perfil else "Sin perfil",
                causales=[perfil_score_res.causal_forzada.codigo]
                if perfil_score_res.causal_forzada and not score_es_exclusion
                else [],
                detalle=[perfil_score_res.razon],
            )
        )

        meses_cont = (
            valor_ingreso.resumen_general.meses_continuidad if valor_ingreso and valor_ingreso.resumen_general else None
        )
        perfil_ingreso_res = asignar_perfil_ingreso(ingreso_smmlv, solicitud, parametros, meses_cont)
        if perfil_ingreso_res.causal_forzada and not score_es_exclusion:
            causales.append(perfil_ingreso_res.causal_forzada)
        traza.append(
            PasoTraza(
                etapa="perfil_ingreso",
                resultado=perfil_ingreso_res.perfil.value if perfil_ingreso_res.perfil else "Sin perfil",
                causales=[perfil_ingreso_res.causal_forzada.codigo]
                if perfil_ingreso_res.causal_forzada and not score_es_exclusion
                else [],
                detalle=[perfil_ingreso_res.razon],
            )
        )

        # --- 5. Matriz de decisión ---
        if score_es_exclusion:
            decision_res = ResultadoDecision(Decision.APROBADO, None, "No aplica: exclusión de score")
        elif score_exclusion_ignorada:
            decision_res = ResultadoDecision(
                Decision.APROBADO,
                None,
                "Exclusión de score desactivada; continúa evaluación de ingresos y capacidad",
            )
        else:
            decision_res = decidir_por_ocupacion(
                solicitud, perfil_score_res.perfil, perfil_ingreso_res.perfil, parametros
            )
            if decision_res.causal:
                causales.append(decision_res.causal)
        traza.append(
            PasoTraza(
                etapa="matriz_decision",
                resultado=decision_res.decision.value,
                causales=[decision_res.causal.codigo] if decision_res.causal else [],
                detalle=[decision_res.razon],
            )
        )

        # --- 6. Capacidad de pago ---
        capacidad: ResultadoCapacidadPago = calcular_capacidad_pago(
            hdc, solicitud, parametros, ingreso_final, ingreso_smmlv, ingreso_res.fuente
        )
        causales += capacidad.causales
        traza.append(
            PasoTraza(
                etapa="capacidad_pago",
                resultado=f"Endeudamiento {capacidad.endeudamiento:.2f}% | capacidad {capacidad.capacidad_pago:.0f}",
                causales=[c.codigo for c in capacidad.causales],
                detalle=capacidad.detalles,
            )
        )

        # --- Decisión ---
        # Nunca se aprueba por omisión: si la matriz no pudo aprobar y
        # ninguna etapa dejó causal explícita, se reporta R20.
        if decision_res.decision != Decision.APROBADO and not causales:
            causales.append(Causal.R20)
        causales_finales = ordenar_causales(causales)
        if causales_finales:
            decision_interna = max((c.tipo for c in causales_finales), key=PRIORIDAD_DECISION.get)
            # Conservar REQUIERE_CODEUDOR y ESTUDIO para trazabilidad interna
            # La decisión pública continúa siendo binaria
            decision_publica = DecisionFinal.RECHAZADO
        else:
            decision_interna = Decision.APROBADO
            decision_publica = DecisionFinal.APROBADO

        resultado = ResultadoMotor(
            evaluacion_id=evaluacion_id,
            fecha_evaluacion=datetime.now(),
            ambiente=self.ambiente,
            solicitud=solicitud,
            decision=decision_publica,
            decision_interna=decision_interna,
            causales=causales_finales,
            score_consultado=score,
            score_tipo=score_tipo,
            perfil_score=perfil_score_res.perfil,
            quanto_medio=_q(quanto_pesos),
            valor_ingreso=_q(val_ingreso),
            ingreso_final=_q(ingreso_final),
            fuente_ingreso_final=ingreso_res.fuente,
            ingreso_final_smmlv=_q(ingreso_smmlv, _CUATRO_DECIMALES),
            smmlv=self.smmlv,
            perfil_ingreso=perfil_ingreso_res.perfil,
            gastos_financieros_no_rotativos=_q(capacidad.gastos_financieros_no_rotativos),
            gasto_financiero_rotativo=_q(capacidad.gasto_financiero_rotativo),
            gastos_personales=_q(capacidad.gastos_personales),
            endeudamiento=_q(capacidad.endeudamiento),
            disponible=_q(capacidad.disponible),
            capacidad_pago=_q(capacidad.capacidad_pago),
            cupo_sugerido=_q(capacidad.cupo_sugerido),
            cuota_sugerida=_q(capacidad.cuota_sugerida),
            cuota_moto=_q(capacidad.cuota_moto),
            indicadores_buro={
                **asdict(filtros.indicadores),
                "documento_vigente": filtros.indicadores.documento_vigente,
                "score_codigo_exclusion": exclusion.codigo_exclusion,
                "reportado_fallecido": exclusion.fallecido,
            },
            trazabilidad=traza,
            advertencias=advertencias,
            parametros_usados=parametros.snapshot(),
            tiempo_ms=int((time.perf_counter() - t_inicio) * 1000),
            hdc_respuesta=hdc,
            valor_ingreso_respuesta=valor_ingreso,
        )
        logger.info(
            "Evaluación completa | id=%s | decision=%s | interna=%s | causales=%s",
            evaluacion_id,
            decision_publica.value,
            decision_interna.value,
            [c.codigo for c in causales_finales],
        )
        return resultado
