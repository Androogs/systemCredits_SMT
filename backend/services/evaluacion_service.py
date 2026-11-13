"""
Orquestación de una evaluación completa: obtiene los reportes del
buró, valida identidad, ejecuta el motor puro (MotorDecision) y
persiste el resultado.

Fuentes de reportes:
    - "experian": consulta en línea HDC+ y Valor Ingreso. Obligatoria
      en ambiente produccion.
    - "mock:<escenario>": reportes ficticios, SOLO ambiente demo.
    - "archivos": JSON/PDF exportados de Experian (CLI evaluar_local).
    - "cotizantes": Valor Ingreso tomado de cotizante /
      cotizante_ingreso_mensual ya almacenados (flujo por id_solicitud).

Ahorro de consumo (BRD): con consulta en línea, si HDC+ ya dispara una
causal de RECHAZO, no se consulta Valor Ingreso; el motor completa la
evaluación con la fuente aplicable a la ocupación (VI o Quanto) y lo
deja advertido.

Persistencia:
    - Siempre: fila en motor_evaluacion_auditoria.
    - Flujo por id_solicitud (esquema SUMOTO): evaluacion_credito,
      capacidad_pago, solicitud_causal, solicitud_credito.decision y, si
      queda APROBADA, ofertas por producto de aliado (elegibilidad).
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.config import Settings, get_settings
from backend.integrations.datacredito.hdc_client import HDCRestClient
from backend.integrations.datacredito.income_client import IncomeRestClient
from backend.integrations.datacredito.mock_buro import crear_escenario
from backend.integrations.simit.client import (
    ResultadoSimit,
    crear_cliente_simit,
)
from backend.repositories.consulta_simit_repository import ConsultaSimitRepository
from backend.integrations.simit.mock_simit import resultado_mock as simit_mock
from backend.models.buro_models import HDC_CODIGO_CONSULTA_EFECTIVA, RespuestaHDC, RespuestaValorIngreso
from backend.models.enums import Causal, Decision, DecisionFinal, Ocupacion, TipoContrato, TipoIdentificacion
from backend.models.motor_models import (
    EvaluarRequest,
    EvaluarSolicitudRequest,
    IngresoPropioRequest,
    IngresoPropioResponse,
    PasoTraza,
    ResultadoMotor,
    Solicitud,
)
from backend.repositories.auditoria_repository import AuditoriaRepository
from backend.repositories.consulta_buro_repository import ConsultaBuroRepository
from backend.repositories.evaluacion_repository import EvaluacionRepository
from backend.repositories.solicitud_repository import SolicitudRepository
from backend.services.documento_service import DocumentoService
from backend.services.elegibilidad_service import EligibilidadService
from backend.services.mapeos_db import (
    DECISION_A_DB,
    OCUPACION_DESDE_DB,
    TIPO_CONTRATO_DESDE_DB,
    estado_solicitud,
)
from backend.services.motor_decision_service import MotorDecision, extraer_score
from backend.services.motor_exceptions import (
    DataCreditoError,
    ReporteBuroNoEvaluableError,
    SolicitudNoEncontradaError,
    ValidacionError,
)
from backend.services.motor_parametros import MotorParametros, ParametrosStore
from backend.services.reglas_filtros_duros import evaluar_exclusion_score, evaluar_filtros_duros
from backend.services.seguro_service import seguro_vida_vigente
from backend.services.validaciones_identidad import advertencias_consistencia, validar_identidad
from backend.services.valor_ingreso_service import (
    aportantes_desde_cotizantes,
    calcular_valor_ingreso_aportantes,
    respuesta_desde_cotizantes,
)
from backend.utils.fechas import calcular_edad
from backend.utils.loggers import get_logger

logger = get_logger("motor_decision.evaluacion")

@dataclass
class ReportesBuro:
    hdc: RespuestaHDC
    valor_ingreso: RespuestaValorIngreso | None
    origen: str
    advertencias: list[str] = field(default_factory=list)


def _hdc_reporta_fallecimiento(hdc: RespuestaHDC, params: MotorParametros | None = None) -> bool:
    """Permite evaluar el rechazo R1 aunque HDC responda sin reporte evaluable."""
    if params is not None and not params.activar_exclusion_score_3_fallecido:
        return False
    return any(score.puntaje == 3 for score in hdc.scores if score.puntaje is not None)


class EvaluacionService:
    def __init__(
        self,
        db: Session | None,
        settings: Settings | None = None,
        store: ParametrosStore | None = None,
        hdc_client: HDCRestClient | None = None,
        income_client: IncomeRestClient | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.store = store or ParametrosStore(self.settings.parametros_path)
        self._hdc_client = hdc_client
        self._income_client = income_client

    # ------------------------------------------------------------------
    # Obtención de reportes
    # ------------------------------------------------------------------
    def _obtener_reportes(
        self,
        solicitud: Solicitud,
        params: MotorParametros,
        consultar_experian: bool,
        escenario_mock: str | None,
        id_solicitud=None,
    ) -> ReportesBuro:
        en_linea = consultar_experian or self.settings.environment == "produccion"
        if not en_linea:
            escenario = escenario_mock or "aprobado"
            try:
                hdc, vi = crear_escenario(
                    escenario,
                    solicitud.tipo_id,
                    solicitud.numero_id,
                    solicitud.primer_apellido,
                    self.settings.smmlv,
                )
            except ValueError as exc:
                raise ValidacionError(str(exc)) from exc
            return ReportesBuro(hdc, vi, f"mock:{escenario}")

        if escenario_mock:
            raise ValidacionError("escenario_mock solo se permite en ambiente demo sin consulta en línea.")

        # La consulta a centrales es un recurso pago por persona: si hay
        # un reporte vigente se reutiliza y el motor corre sobre esos
        # datos (los parámetros vigentes siempre aplican de nuevo).
        cache_repo = (
            ConsultaBuroRepository(self.db)
            if self.db is not None and self.settings.buro_cache_habilitado
            else None
        )
        if cache_repo is not None:
            previa = cache_repo.ultima_vigente(
                solicitud.tipo_id.value, solicitud.numero_id, self.settings.buro_cache_dias
            )
            if previa is not None:
                hdc_prev, vi_prev = previa.a_reportes()
                logger.info(
                    "Reuso de consulta a centrales vigente",
                    extra={
                        "numero_id": solicitud.numero_id,
                        "consulta_id": previa.id_consulta,
                        "fecha_consulta": previa.fecha_consulta.isoformat(),
                    },
                )
                return ReportesBuro(
                    hdc_prev,
                    vi_prev,
                    f"cache:{previa.origen}",
                    [
                        f"Reporte de centrales reutilizado (consulta {previa.fecha_consulta:%Y-%m-%d}, "
                        f"vigente {self.settings.buro_cache_dias} días)."
                    ],
                )

        faltantes = self.settings.configuracion_experian_faltante()
        if faltantes:
            raise DataCreditoError(
                "configuracion", None, "Falta configuración de Experian en .env: " + ", ".join(faltantes)
            )

        hdc_client = self._hdc_client or HDCRestClient(self.settings)
        hdc = hdc_client.consultar(solicitud.tipo_id, solicitud.numero_id, solicitud.primer_apellido)
        if hdc.respuesta_codigo != HDC_CODIGO_CONSULTA_EFECTIVA and not _hdc_reporta_fallecimiento(hdc, params):
            raise ReporteBuroNoEvaluableError(hdc.respuesta_codigo, hdc.respuesta_desc)
        validar_identidad(solicitud, hdc, None)

        if _hdc_reporta_fallecimiento(hdc, params):
            reportes = ReportesBuro(
                hdc,
                None,
                "experian",
                ["Valor Ingreso no consultado: HDC+ reporta al cliente como fallecido."],
            )
        else:
            # BRD: con una causal de rechazo activa no se consume Valor Ingreso.
            score, _ = extraer_score(hdc, params)
            preliminar = evaluar_filtros_duros(hdc, solicitud, params, date.today(), evaluar_exclusion_score(score, params))
            rechazos = [c.causal.codigo for c in preliminar.causales if c.causal.tipo == Decision.RECHAZADO]
            if rechazos:
                reportes = ReportesBuro(
                    hdc,
                    None,
                    "experian",
                    [f"Valor Ingreso no consultado: HDC+ ya dispara causales de rechazo ({', '.join(rechazos)})."],
                )
            else:
                income_client = self._income_client or IncomeRestClient(self.settings)
                vi = income_client.consultar(
                    solicitud.tipo_id, solicitud.numero_id, ingreso_validar=int(solicitud.ingresos_mensuales)
                )
                reportes = ReportesBuro(hdc, vi, "experian")

        if cache_repo is not None:
            cache_repo.registrar(
                solicitud.tipo_id.value,
                solicitud.numero_id,
                id_solicitud,
                reportes.hdc,
                reportes.valor_ingreso,
                reportes.origen,
            )
        return reportes

    # ------------------------------------------------------------------
    # Pre-filtro SIMIT (deuda de tránsito)
    # ------------------------------------------------------------------
    def _consultar_simit(
        self,
        solicitud: Solicitud,
        en_linea: bool,
        escenario_mock: str | None,
        id_solicitud=None,
    ) -> ResultadoSimit | None:
        """Paz y salvo de tránsito antes de gastar la consulta de buró.

        Declarado en la solicitud → rechazo sintético; en demo responde
        el mock por escenario (SIMIT_MOCK_EN_DEMO); en línea usa el
        proveedor de `simit_proveedor` con el caché por documento (el
        precache del consentimiento ya dejó la fila). Si el proveedor
        falla: fail-open por defecto (la evaluación sigue sin el
        pre-filtro), salvo simit_requerido.
        """
        if not self.settings.simit_habilitado:
            return None
        # El cliente ya lo declaró en la solicitud: no hace falta
        # verificarlo — la propia declaración dispara R22.
        if solicitud.tiene_multas_runt:
            return ResultadoSimit(
                paz_y_salvo=False,
                total_deuda=Decimal(0),
                total_items=0,
                origen="declarado en la solicitud",
            )
        # El mock por escenario solo aplica a la evaluación en demo: la
        # puerta SIMIT del paso 3 y el precache del consentimiento
        # consultan siempre el proveedor real.
        if self.settings.environment == "demo" and self.settings.simit_mock_en_demo:
            return simit_mock(escenario_mock)
        if not en_linea:
            return None
        if (
            (self.settings.simit_proveedor or "").lower() == "placapi"
            and not self.settings.simit_api_key
        ):
            logger.warning(
                "SIMIT en línea sin API key (SIMIT_API_KEY): se omite el pre-filtro"
            )
            return None
        try:
            return self.consultar_simit_en_linea(
                solicitud.tipo_id,
                solicitud.numero_id,
                id_solicitud=id_solicitud,
            )
        except DataCreditoError as exc:
            if self.settings.simit_requerido:
                raise ValidacionError(
                    f"No se pudo consultar el estado de cuenta de tránsito (SIMIT): {exc.message}"
                ) from exc
            logger.warning(
                "SIMIT no respondió; la evaluación sigue sin el pre-filtro | %s",
                exc.message,
            )
            return None

    def consultar_simit_en_linea(
        self,
        tipo_id: TipoIdentificacion,
        numero_id: str,
        id_solicitud=None,
        usar_cache: bool = True,
    ) -> ResultadoSimit:
        """Proveedor SIMIT configurado con caché por documento.

        A diferencia de `_consultar_simit` (que decide mock/fail-open
        para la evaluación), este método propaga `DataCreditoError`:
        lo usan la evaluación en línea y el precache que corre en
        background al registrar el consentimiento Habeas Data.
        """
        repo = (
            ConsultaSimitRepository(self.db)
            if self.db is not None and self.settings.simit_cache_dias > 0
            else None
        )
        if usar_cache and repo is not None:
            previa = repo.ultima_vigente(
                tipo_id.value, numero_id, self.settings.simit_cache_dias
            )
            if previa is not None:
                logger.info(
                    "Reuso de consulta SIMIT vigente",
                    extra={
                        "numero_id": numero_id,
                        "consulta_id": previa.id_consulta,
                        "fecha_consulta": previa.fecha_consulta.isoformat(),
                    },
                )
                return repo.a_resultado(previa)
        resultado = crear_cliente_simit(self.settings).estado_cuenta_transito(
            tipo_id, numero_id
        )
        if repo is not None:
            repo.registrar(tipo_id.value, numero_id, id_solicitud, resultado)
        return resultado

    def _rechazo_simit(
        self, solicitud: Solicitud, simit: ResultadoSimit
    ) -> ResultadoMotor:
        """Rechazo del pre-filtro: R22 con trazabilidad del hallazgo,
        sin haber consumido la consulta de buró."""
        declarado = simit.origen == "declarado en la solicitud"
        solicitud.tiene_multas_runt = True
        detalle = (
            "El cliente declaró multas pendientes en la solicitud; "
            "no se consumió la consulta de buró."
            if declarado
            else "Estado de cuenta de tránsito "
            f"({simit.origen}): deuda pendiente "
            f"{simit.total_deuda:,.0f} COP en "
            f"{simit.total_items} registro(s); no se "
            "consumió la consulta de buró."
        )
        return ResultadoMotor(
            evaluacion_id=str(uuid.uuid4()),
            fecha_evaluacion=datetime.now(UTC),
            ambiente=self.settings.environment,
            solicitud=solicitud,
            decision=DecisionFinal.RECHAZADO,
            decision_interna=Decision.RECHAZADO,
            causales=[Causal.R22],
            smmlv=self.settings.smmlv,
            trazabilidad=[
                PasoTraza(
                    etapa="Pre-filtro SIMIT",
                    resultado="rechazado",
                    causales=["R22"],
                    detalle=[detalle],
                )
            ],
        )

    # ------------------------------------------------------------------
    # Evaluación
    # ------------------------------------------------------------------
    def evaluar_con_reportes(
        self,
        solicitud: Solicitud,
        hdc: RespuestaHDC,
        valor_ingreso: RespuestaValorIngreso | None,
        advertencias: list[str] | None = None,
        params: MotorParametros | None = None,
    ) -> ResultadoMotor:
        """Valida identidad y ejecuta el motor puro. No persiste."""
        params = params or self.store.cargar()
        validar_identidad(solicitud, hdc, valor_ingreso)
        advertencias = [*(advertencias or []), *advertencias_consistencia(solicitud, hdc, valor_ingreso)]
        motor = MotorDecision(smmlv=self.settings.smmlv, ambiente=self.settings.environment)
        return motor.evaluar(solicitud, hdc, valor_ingreso, params, advertencias=advertencias)

    def evaluar_payload(self, req: EvaluarRequest) -> ResultadoMotor:
        """POST /motor/evaluar."""
        solicitud = req.a_solicitud()
        params = self.store.cargar()
        en_linea = req.consultar_experian or self.settings.environment == "produccion"
        origen = "evaluacion"
        simit = self._consultar_simit(solicitud, en_linea, req.escenario_mock)
        if simit is not None and not simit.paz_y_salvo:
            resultado = self._rechazo_simit(solicitud, simit)
            origen = simit.origen
        else:
            reportes = self._obtener_reportes(solicitud, params, req.consultar_experian, req.escenario_mock)
            resultado = self.evaluar_con_reportes(
                solicitud, reportes.hdc, reportes.valor_ingreso, reportes.advertencias, params
            )
            origen = reportes.origen
        if self.db is not None:
            AuditoriaRepository(self.db).guardar(resultado, origen, parametros_huella=params.huella())
        return resultado

    def evaluar_solicitud_db(self, id_solicitud: uuid.UUID, req: EvaluarSolicitudRequest) -> ResultadoMotor:
        """POST /solicitudes/{id}/evaluar: evalúa y persiste en el esquema SUMOTO."""
        if self.db is None:
            raise ValidacionError("Se requiere base de datos para evaluar una solicitud almacenada.")
        repo = SolicitudRepository(self.db)
        sc = repo.obtener_con_datos_para_evaluar(id_solicitud)
        if sc is None:
            raise SolicitudNoEncontradaError(f"No existe la solicitud {id_solicitud}")
        solicitud = self._solicitud_desde_db(sc, req)

        params = self.store.cargar()
        en_linea = req.consultar_experian or self.settings.environment == "produccion"
        simit = self._consultar_simit(
            solicitud, en_linea, req.escenario_mock, id_solicitud=id_solicitud
        )
        origen = "evaluacion"
        if simit is not None and not simit.paz_y_salvo:
            resultado = self._rechazo_simit(solicitud, simit)
            origen = simit.origen
        else:
            reportes = self._obtener_reportes(
                solicitud, params, req.consultar_experian, req.escenario_mock, id_solicitud
            )
            if not req.consultar_experian and self.settings.environment == "demo":
                vi_db = respuesta_desde_cotizantes(sc.cotizantes)
                if vi_db is not None:
                    reportes.valor_ingreso = vi_db
                    reportes.origen = f"{reportes.origen}+cotizantes"
            resultado = self.evaluar_con_reportes(
                solicitud, reportes.hdc, reportes.valor_ingreso, reportes.advertencias, params
            )
            origen = reportes.origen

        eval_repo = EvaluacionRepository(self.db)
        eval_repo.crear_evaluacion_motor(id_solicitud, resultado)
        eval_repo.crear_capacidad_pago(id_solicitud, resultado)
        eval_repo.reemplazar_causales(id_solicitud, resultado)
        repo.actualizar_decision(
            id_solicitud,
            DECISION_A_DB[resultado.decision],
            estado=estado_solicitud(resultado),
            descripcion_estado="; ".join(c.value for c in resultado.causales) or None,
        )
        if resultado.decision == DecisionFinal.APROBADO:
            self._generar_ofertas(id_solicitud, resultado, repo)
        AuditoriaRepository(self.db).guardar(resultado, origen, str(id_solicitud), parametros_huella=params.huella())
        try:
            with self.db.begin_nested():
                # Soporte documental de la radicación (autorización de
                # centrales + solicitud de crédito): la consulta al buró
                # ya se hizo con el consentimiento del cliente — el
                # expediente la evidencia haya o no aprobación.
                DocumentoService(self.db).generar_paquete_radicacion(id_solicitud)
        except Exception:
            logger.exception(
                "No se pudo generar el paquete de radicación de la solicitud %s",
                id_solicitud,
            )
        return resultado

    def _solicitud_desde_db(self, sc, req: EvaluarSolicitudRequest) -> Solicitud:
        cliente, laborales = sc.cliente, sc.datos_laborales
        if cliente is None:
            raise ValidacionError(f"La solicitud {sc.id_solicitud} no tiene cliente.")
        if laborales is None:
            raise ValidacionError(f"La solicitud {sc.id_solicitud} no tiene datos_laborales.")
        if not cliente.ocupacion:
            raise ValidacionError(f"El cliente de la solicitud {sc.id_solicitud} no tiene ocupación registrada.")
        apellido = req.primer_apellido or cliente.primer_apellido
        if not apellido:
            raise ValidacionError("Falta el primer apellido del cliente (HDC+ lo exige): envíalo en el request.")
        try:
            tipo_id = TipoIdentificacion(str(cliente.tipo_documento))
        except ValueError:
            try:
                tipo_id = TipoIdentificacion[str(cliente.tipo_documento).upper()]
            except KeyError as exc:
                raise ValidacionError(f"Tipo de documento no reconocido: {cliente.tipo_documento}") from exc
        tipo_contrato = None
        if laborales.tipo_contrato:
            tipo_contrato = TIPO_CONTRATO_DESDE_DB.get(laborales.tipo_contrato.strip().lower().replace(" ", "_"))
            if tipo_contrato is None:
                raise ValidacionError(f"Tipo de contrato no reconocido: {laborales.tipo_contrato}")
        ocupacion = OCUPACION_DESDE_DB.get(str(cliente.ocupacion).strip().lower().replace(" ", "_"))
        if ocupacion is None:
            try:
                ocupacion = Ocupacion(str(cliente.ocupacion))
            except ValueError as exc:
                raise ValidacionError(f"Ocupación no reconocida: {cliente.ocupacion}") from exc
        return Solicitud(
            tipo_id=tipo_id,
            numero_id=cliente.num_cedula,
            primer_apellido=apellido,
            ocupacion=ocupacion,
            tipo_contrato=tipo_contrato,
            antiguedad_meses=laborales.meses_continuidad,
            anios_camara_comercio=laborales.anios_camara_comercio,
            fecha_nacimiento=cliente.fecha_nacimiento,
            nacionalidad=cliente.nacionalidad or "Colombia",
            tiene_multas_runt=req.tiene_multas_runt,
            ingresos_mensuales=laborales.ingreso_mensual or 0,
            otros_ingresos=laborales.otros_ingresos or 0,
            saldo_financiar=req.saldo_financiar,
            plazo=req.plazo,
            tasa=req.tasa,
        )

    def _generar_ofertas(self, id_solicitud: uuid.UUID, resultado: ResultadoMotor, repo: SolicitudRepository) -> None:
        productos = repo.productos_activos()
        if not productos:
            return
        s = resultado.solicitud
        datos = {
            "score": resultado.score_consultado,
            "perfil_score": resultado.perfil_score.value if resultado.perfil_score else None,
            "perfil_ingreso": resultado.perfil_ingreso.value if resultado.perfil_ingreso else None,
            "ingreso_final": resultado.ingreso_final,
            "ingreso_final_smmlv": resultado.ingreso_final_smmlv,
            "endeudamiento": resultado.endeudamiento,
            "capacidad_pago": resultado.capacidad_pago,
            "cupo_sugerido": resultado.cupo_sugerido,
            "edad": calcular_edad(s.fecha_nacimiento, resultado.fecha_evaluacion.date()),
            "ocupacion": s.ocupacion.value,
            "monto_solicitado": s.saldo_financiar,
            "plazo": s.plazo,
            "tasa_referencia": s.tasa,
            "prima_seguro_pct": self._prima_seguro_vida(),
        }
        servicio = EligibilidadService()
        ofertas = [servicio.evaluar_producto(id_solicitud, p, datos) for p in productos]
        vigencia = datetime.now(UTC) + timedelta(days=self.settings.oferta_vigencia_dias)
        for oferta in ofertas:
            oferta.fecha_vigencia = vigencia
        repo.guardar_ofertas(ofertas)

    def _prima_seguro_vida(self) -> Decimal | None:
        """Tasa de prima vigente del seguro de vida deudores (catálogo)."""
        if self.db is None:
            return None
        seguro = seguro_vida_vigente(self.db)
        return Decimal(str(seguro.tasa_prima)) if seguro is not None else None

    # ------------------------------------------------------------------
    # Valor Ingreso propio (cotizantes almacenados)
    # ------------------------------------------------------------------
    def calcular_ingreso_propio(self, req: IngresoPropioRequest) -> IngresoPropioResponse:
        if self.db is None:
            raise ValidacionError("Se requiere base de datos.")
        sc = SolicitudRepository(self.db).obtener_con_datos_para_evaluar(req.id_solicitud)
        if sc is None:
            raise SolicitudNoEncontradaError(f"No existe la solicitud {req.id_solicitud}")
        params = self.store.cargar()
        aportantes = aportantes_desde_cotizantes(sc.cotizantes)
        valor = calcular_valor_ingreso_aportantes(aportantes, params.max_aportantes, req.meses_a_promediar)
        return IngresoPropioResponse(
            id_solicitud=req.id_solicitud,
            valor_ingreso=valor.quantize(Decimal("0.01")),
            aportantes_considerados=min(len(aportantes), params.max_aportantes),
            meses_a_promediar=req.meses_a_promediar,
        )
