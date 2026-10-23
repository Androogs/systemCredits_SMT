"""
Parámetros de negocio del motor de decisión.

Fuente de los valores por defecto: PPT v4 (2026 Motor de Decisión),
que coincide con el BRD-Prefiltro_Cliente_InversionesPacifico en
cortes de score, ingreso, continuidad y cámara de comercio. Donde las
dos fuentes diferían se tomó la PPT v4 (ver docs/bitacora_ensamble.md).

Los nombres siguen las variables del BRD (Score_EP_1, Ingreso_E_2,
Meses_Cont_1, Saldo_Mora_BE, ...) para que la trazabilidad contra el
documento sea directa.

Orden de carga (el último gana):
    1. Defaults de esta clase.
    2. Archivo JSON (PARAMETROS_PATH, por defecto ./parametros.json),
       editable desde la API /parametros.
    3. Variables de entorno MOTOR_<CAMPO> (ej. MOTOR_ENDEU_1=88), para
       bloquear un valor en un despliegue sin tocar código ni archivo.

Todo el conjunto se valida al cargar: escaleras descendentes,
porcentajes entre 0 y 100, umbrales coherentes. Un archivo incoherente
detiene la evaluación (ParametrosError) en vez de decidir con él.
"""

import hashlib
import json
import os
import threading
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from backend.services.motor_exceptions import ParametrosError
from backend.utils.loggers import get_logger

logger = get_logger("motor_decision.parametros")

_ENV_PREFIX = "MOTOR_"


class MotorParametros(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    # --- Política de edad (PPT v4: >= 18 y < 66) ---
    edad_minima_be: int = Field(18, ge=0)
    edad_maxima_be: int = Field(66, gt=0, description="Límite EXCLUSIVO: edad < edad_maxima_be")

    # False = ignorar la exclusión y continuar por el flujo normal.
    activar_exclusion_persona_juridica: bool = True
    activar_exclusion_score_0: bool = True
    activar_exclusion_score_3_fallecido: bool = True
    activar_exclusion_score_4_codeudor: bool = True
    scores_exclusion: list[int] = Field(default_factory=lambda: [0, 4])

    # --- Telcos: saldo en mora mínimo para que cuenten (PPT v4 pág. 6) ---
    saldo_mora_be: Decimal = Field(Decimal("300000"), ge=0)
    # Estados HDC+ de cuentas de ahorro/corriente: 06 = Embargada;
    # 07 = Embargada activa (continúa en funcionamiento pese al embargo).
    estados_buro_embargo: list[str] = Field(default_factory=lambda: ["06", "07"])
    # Estados de pago HDC+: 45 = Cartera castigada; 47 = Dudoso recaudo;
    # 03 = Pago total/cierre de la obligación.
    estados_buro_cartera_castigada: list[str] = Field(default_factory=lambda: ["45"])
    estados_buro_dudoso_recaudo: list[str] = Field(default_factory=lambda: ["47"])
    estados_buro_pago_total: list[str] = Field(default_factory=lambda: ["03"])
    # Evento HDC+ 03 = Cancelación por mal manejo.
    evento_cancelacion_mal_manejo: str = "03"
    calificaciones_negativas: list[str] = Field(default_factory=lambda: ["C", "D", "E", "K"])
    codigos_reestructuracion: list[str] = Field(default_factory=lambda: ["12", "1", "2", "5", "6"])
    tokens_reestructuracion: list[str] = Field(default_factory=lambda: ["REESTRUCT", "REFINANC", "RENEGOCI"])

    # --- Perfil de score: Empleado / Pensionado (BRD 2.4.5) ---
    score_ep_1: Decimal = Decimal("750")  # >= -> A
    score_ep_2: Decimal = Decimal("680")  # >= -> B
    score_ep_3: Decimal = Decimal("600")  # >= -> C
    score_ep_4: Decimal = Decimal("500")  # >= -> D ; < -> Rechazo
    # --- Perfil de score: Independiente / Fuerzas Militares ---
    score_if_1: Decimal = Decimal("770")
    score_if_2: Decimal = Decimal("700")
    score_if_3: Decimal = Decimal("620")
    score_if_4: Decimal = Decimal("520")
    # Piso común (BRD): score < piso -> "Cliente sin experiencia crediticia"
    score_piso_experiencia: Decimal = Field(Decimal("150"), ge=0)
    # Códigos de modelo de score aceptados, en orden de preferencia.
    # Si ninguno aparece en HDC+, NO se sustituye por otro score.
    codigos_score: list[str] = Field(default_factory=lambda: ["67", "Z0", "BF", "DF", "04"])
    quanto_factor: Decimal = Field(Decimal("1000"), gt=0)

    # --- Perfil de ingreso en SMMLV (BRD 2.4.6) ---
    ingreso_e_1: Decimal = Decimal("1.6")  # Empleado ALTO
    ingreso_e_2: Decimal = Decimal("1.4")  # Empleado MEDIO
    ingreso_e_3: Decimal = Decimal("1.0")  # Empleado BAJO (piso)
    ingreso_pf_1: Decimal = Decimal("1.6")  # Pensionado / FFMM ALTO
    ingreso_pf_2: Decimal = Decimal("1.4")
    ingreso_pf_3: Decimal = Decimal("1.0")
    ingreso_i_1: Decimal = Decimal("2.5")  # Independiente ALTO
    ingreso_i_2: Decimal = Decimal("2.0")  # Independiente MEDIO
    ingreso_i_3: Decimal = Decimal("1.6")  # Independiente BAJO
    ingreso_i_4: Decimal = Decimal("1.4")  # Independiente GRIS (> exclusivo)

    # --- Continuidad laboral (Valor Ingreso), meses ---
    meses_cont_1: int = Field(5, ge=0)  # Contrato indefinido
    meses_cont_2: int = Field(10, ge=0)  # Contrato fijo / obra o labor

    # --- Años mínimos de Cámara de Comercio (Independiente) ---
    anios_cam_1: Decimal = Decimal("1")  # perfil ALTO
    anios_cam_2: Decimal = Decimal("2")  # perfil MEDIO
    anios_cam_3: Decimal = Decimal("3")  # perfil BAJO
    anios_cam_4: Decimal = Decimal("4")  # perfil GRIS / score D

    # --- Umbrales de conteo de políticas de buró (BRD tabla 2.4.1) ---
    meses_ventana_buro: int = Field(12, ge=1)
    umbral_mora_30_historica: int = Field(2, ge=1)
    umbral_mora_60_historica: int = Field(1, ge=1)
    umbral_mora_90_historica: int = Field(1, ge=1)
    umbral_reestructuraciones: int = Field(2, ge=1)

    # --- Gastos personales por banda de SMMLV (PPT v4 pág. 10) ---
    gastos_personales_pct_bajo: Decimal = Decimal("50")  # SMMLV < umbral_medio
    gastos_personales_pct_medio: Decimal = Decimal("45")  # umbral_medio <= SMMLV < umbral_alto
    gastos_personales_pct_alto: Decimal = Decimal("40")  # SMMLV >= umbral_alto
    gastos_personales_umbral_medio: Decimal = Decimal("1.6")
    gastos_personales_umbral_alto: Decimal = Decimal("2.0")
    gastos_personales_pct_quanto: Decimal = Decimal("50")

    # --- Endeudamiento (PPT v4) ---
    endeu_1: Decimal = Decimal("90")  # > endeu_1 -> Rechazo (R17)
    endeu_2: Decimal = Decimal("86")  # endeu_2 <= x <= endeu_1 -> Rechazo (R17)

    # --- Capacidad de pago (PPT v4 pág. 11) ---
    capacidad_pago_pct: Decimal = Decimal("70")
    
    # Nuevo en v5: Capacidad de pago diferenciada por tipo de ocupación
    # Esto permite calcular diferentes porcentajes de capacidad de pago según la ocupación del cliente
    # Valores por defecto: Empleado 70%, Pensionado/Fuerzas Militares 65%, Independiente 60%
    capacidad_pago_pct_empleado: Decimal = Decimal("70")  # Para empleados y pensionados
    capacidad_pago_pct_independiente: Decimal = Decimal("60")  # Para trabajadores independientes
    capacidad_pago_pct_ffmm: Decimal = Decimal("65")  # Para fuerzas militares
    
    # Nuevo en v5: Factor de ajuste por riesgo de comportamiento de pago
    # Ajusta la capacidad de pago basada en el historial de comportamiento del cliente
    # Valores: bajo riesgo (1.0), riesgo moderado (0.9), alto riesgo (0.8)
    capacidad_pago_factor_comportamiento: Decimal = Decimal("1.0")
    
    # Nuevo en v5: Límite máximo de cuota calculado basado en ingresos
    # La capacidad de pago no puede exceder este límite adicional basado en los ingresos declarados
    capacidad_pago_limite_ingresos_pct: Decimal = Decimal("0.85")  # No puede exceder 85% de los ingresos
    
    # --- Cupo sugerido (PPT v4) ---
    cupo_sugerido_tasa_pct: Decimal = Decimal("2")
    cupo_sugerido_plazo_meses: int = Field(24, ge=1)
    cupo_sugerido_tope: Decimal = Field(Decimal("20000000"), gt=0)
    
    # --- Gasto financiero estimado cuando el buró no reporta cuota ---
    tasa_gasto_financiero_pct: Decimal = Decimal("2")
    plazo_rotativo_default_meses: int = Field(36, ge=1)
    
    # --- Nuevo en v5: Ajustes por variante geográfica/regional ---
    # Permite diferentes configuraciones por región geográfica
    # Estos valores pueden ser sobrescritos por variables de entorno o configuración específica de región
    capacidad_pago_pct_region_nacional: Decimal = Decimal("70")  # Por defecto, valor nacional
    capacidad_pago_pct_region_costa: Decimal = Decimal("68")  # Costa - menor capacidad de pago debido a mayor costo de vida
    capacidad_pago_pct_region_andina: Decimal = Decimal("72")  # Región andina - mayor capacidad de pago
    capacidad_pago_pct_region_pacifico: Decimal = Decimal("69")  # Pacíco - capacidad de pago intermedia
    
    # --- Nuevo en v5: Consideración de variables macroeconómicas ---
    # Ajusta la capacidad de pago basada en condiciones macroeconómicas generales
    # 1.0 = condiciones normales, 0.95 = condiciones moderadas, 0.9 = condiciones difíciles
    capacidad_pago_factor_macro: Decimal = Decimal("1.0")

    # --- Valor Ingreso (BRD 2.4.3) ---
    max_aportantes: int = Field(5, ge=1)
    meses_promedio_valor_ingreso: int = Field(3, ge=1)

    @model_validator(mode="after")
    def _validar_coherencia(self) -> "MotorParametros":
        errores: list[str] = []

        def descendente(nombres: list[str]) -> None:
            valores = [getattr(self, n) for n in nombres]
            if any(a <= b for a, b in zip(valores, valores[1:], strict=False)):
                errores.append(f"{' > '.join(nombres)} debe ser estrictamente descendente")

        def ascendente(nombres: list[str]) -> None:
            valores = [getattr(self, n) for n in nombres]
            if any(a > b for a, b in zip(valores, valores[1:], strict=False)):
                errores.append(f"{' <= '.join(nombres)} debe ser ascendente")

        descendente(["score_ep_1", "score_ep_2", "score_ep_3", "score_ep_4"])
        descendente(["score_if_1", "score_if_2", "score_if_3", "score_if_4"])
        descendente(["ingreso_e_1", "ingreso_e_2", "ingreso_e_3"])
        descendente(["ingreso_pf_1", "ingreso_pf_2", "ingreso_pf_3"])
        descendente(["ingreso_i_1", "ingreso_i_2", "ingreso_i_3", "ingreso_i_4"])
        ascendente(["anios_cam_1", "anios_cam_2", "anios_cam_3", "anios_cam_4"])

        if self.score_piso_experiencia > min(self.score_ep_4, self.score_if_4):
            errores.append("score_piso_experiencia no puede superar score_ep_4 ni score_if_4")
        if self.edad_minima_be >= self.edad_maxima_be:
            errores.append("edad_minima_be debe ser menor que edad_maxima_be")
        if self.gastos_personales_umbral_medio >= self.gastos_personales_umbral_alto:
            errores.append("gastos_personales_umbral_medio debe ser menor que gastos_personales_umbral_alto")
        if self.endeu_2 >= self.endeu_1:
            errores.append("endeu_2 debe ser menor que endeu_1")
                
        # Validación para nuevos parámetros de capacidad de pago diferenciada por v5
        for nombre in (
            "capacidad_pago_pct_empleado",
            "capacidad_pago_pct_independiente",
            "capacidad_pago_pct_ffmm",
        ):
            valor = getattr(self, nombre)
            if not Decimal(0) <= valor <= Decimal(100):
                errores.append(f"{nombre} debe estar entre 0 y 100")
                
        # Validación para factores de capacidad de pago
        for nombre in (
            "capacidad_pago_factor_comportamiento",
            "capacidad_pago_limite_ingresos_pct",
            "capacidad_pago_factor_macro",
        ):
            valor = getattr(self, nombre)
            if not Decimal(0) <= valor <= Decimal(2):  # Los factores pueden ir de 0.0 a 2.0
                errores.append(f"{nombre} debe estar entre 0.0 y 2.0")
                
        # Validación para capacidades de pago por región
        for nombre in (
            "capacidad_pago_pct_region_nacional",
            "capacidad_pago_pct_region_costa",
            "capacidad_pago_pct_region_andina",
            "capacidad_pago_pct_region_pacifico",
        ):
            valor = getattr(self, nombre)
            if not Decimal(0) <= valor <= Decimal(100):
                errores.append(f"{nombre} debe estar entre 0 y 100")
                
        # Validación de coherencia entre parámetros
        # El factor macroeconómico debe ser menor que el factor regional para evitar sobre-ajuste
        if self.capacidad_pago_factor_macro > Decimal("1.0"):
            errores.append("capacidad_pago_factor_macro no debe exceder 1.0")
            
        # Los factores de comportamiento regional deben ser coherentes
        if self.capacidad_pago_pct_region_costa < Decimal("60"):
            errores.append("capacidad_pago_pct_region_costa debe ser al menos 60 para mantener consistencia regional")
                
        for nombre in (
            "gastos_personales_pct_bajo",
            "gastos_personales_pct_medio",
            "gastos_personales_pct_alto",
            "gastos_personales_pct_quanto",
            "capacidad_pago_pct",
            "cupo_sugerido_tasa_pct",
            "tasa_gasto_financiero_pct",
            "endeu_1",
            "endeu_2",
        ):
            valor = getattr(self, nombre)
            if not Decimal(0) <= valor <= Decimal(100):
                errores.append(f"{nombre} debe estar entre 0 y 100")

        if errores:
            raise ValueError("; ".join(errores))
        return self

    def snapshot(self) -> dict[str, Any]:
        """Valores vigentes serializables con números JSON (auditoría y archivo)."""
        return {k: _a_numero_json(v) for k, v in self.model_dump().items()}

    def huella(self) -> str:
        """Versión del juego de parámetros: sha256 corto del snapshot canónico.

        Dos configuraciones idénticas producen la misma huella; cualquier cambio
        en un parámetro la altera. Se persiste en cada evaluación auditada para
        poder reconstruir el contexto exacto de una decisión.
        """
        canonic = json.dumps(self.snapshot(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonic.encode("utf-8")).hexdigest()[:16]


def _a_numero_json(valor: Any) -> Any:
    if isinstance(valor, Decimal):
        return int(valor) if valor == valor.to_integral_value() else float(valor)
    return valor


PARAMETROS_DEFAULT = MotorParametros().snapshot()


def _overrides_de_entorno() -> dict[str, str]:
    campos = MotorParametros.model_fields
    overrides: dict[str, Any] = {}
    for nombre in campos:
        crudo = os.getenv(f"{_ENV_PREFIX}{nombre.upper()}")
        if crudo is None:
            continue
        if nombre in {
            "codigos_score",
            "estados_buro_embargo",
            "estados_buro_cartera_castigada",
            "estados_buro_dudoso_recaudo",
            "estados_buro_pago_total",
            "calificaciones_negativas",
            "codigos_reestructuracion",
            "tokens_reestructuracion",
        }:
            overrides[nombre] = [c.strip() for c in crudo.split(",") if c.strip()]
        elif nombre == "scores_exclusion":
            overrides[nombre] = [int(c.strip()) for c in crudo.split(",") if c.strip()]
        else:
            overrides[nombre] = crudo
    return overrides


def construir_parametros(datos: dict[str, Any]) -> MotorParametros:
    try:
        return MotorParametros(**datos)
    except ValidationError as exc:
        detalle = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) + ': ' if e['loc'] else ''}{e['msg']}" for e in exc.errors()
        )
        raise ParametrosError(f"Parámetros del motor inválidos: {detalle}") from exc


class ParametrosStore:
    """Carga, valida y guarda los parámetros en un archivo JSON."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def _leer_archivo(self) -> dict[str, Any]:
        if not self.path.exists():
            logger.info("Parámetros: %s no existe, se crea con los valores por defecto", self.path)
            self._escribir(PARAMETROS_DEFAULT)
            return dict(PARAMETROS_DEFAULT)
        try:
            datos = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ParametrosError(f"{self.path} no es un JSON válido: {exc}") from exc
        if not isinstance(datos, dict):
            raise ParametrosError(f"{self.path} debe contener un objeto JSON")
        return datos

    def _escribir(self, datos: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(datos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(self.path)  # escritura atómica

    def cargar(self) -> MotorParametros:
        with self._lock:
            datos = {**PARAMETROS_DEFAULT, **self._leer_archivo(), **_overrides_de_entorno()}
        return construir_parametros(datos)

    def campos_bloqueados_por_entorno(self) -> list[str]:
        return sorted(_overrides_de_entorno())

    def actualizar(self, cambios: dict[str, Any]) -> MotorParametros:
        """Valida el conjunto completo ANTES de guardar; si es incoherente no toca el archivo."""
        with self._lock:
            actual = {**PARAMETROS_DEFAULT, **self._leer_archivo()}
            nuevo = {**actual, **cambios}
            validado = construir_parametros(nuevo)
            self._escribir(validado.snapshot())
        return self.cargar()

    def restablecer(self) -> MotorParametros:
        with self._lock:
            self._escribir(PARAMETROS_DEFAULT)
        return self.cargar()
