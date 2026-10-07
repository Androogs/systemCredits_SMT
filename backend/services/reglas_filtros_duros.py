"""
Filtros duros: exclusiones de score, políticas de la solicitud y
políticas de buró (BRD 2.3, 2.4.1 y 2.4.2 / PPT v4).

Se separan dos responsabilidades:

1. derivar_indicadores_buro(hdc): lee la Historia de Crédito+ y
   produce conteos (IndicadoresBuro). Aquí vive toda la interpretación
   del reporte (vector de comportamiento, estados, sector Telcos,
   codeudor, ventana de 12 meses).
2. evaluar_*: aplican los umbrales de MotorParametros a esos
   indicadores y devuelven las causales disparadas.

Flujo LINEAL (BRD): se evalúan todas las políticas y se devuelven
TODAS las causales que disparen, no solo la primera.

Tabla de políticas de buró (umbral):
     R2  Embargos cuentas corrientes/ahorro (>= 1)
     R3  Cancelaciones por mal manejo, evento 03, últimos 12 meses (>= 1; sin Telcos)
     R4  Cartera castigada últimos 12 meses (>= 1; Telcos si saldo mora > Saldo_Mora_BE)
     R5  Dudoso recaudo últimos 12 meses (>= 1; ídem Telcos)
     R6  Mora vigente numérica 60 días o más, primer carácter 2-6 (>= 1; ídem Telcos)
     R7  Períodos nivel 1 (30 días) en últimos 12 meses (>= umbral_mora_30_historica)
     R8  Períodos nivel 2 (60 días) en últimos 12 meses (>= umbral_mora_60_historica)
     R9  Períodos niveles 3-6 (90+ días) en últimos 12 meses (>= umbral_mora_90_historica)
     R10 Calificación C, D, E, K (>= 1; todos los sectores, sin codeudor)
     R11 Obligaciones reestructuradas últimos 12 meses (>= umbral_reestructuraciones)
     R12 Estado de documento diferente a vigente (00; 25 = excepción CE)
     E2  Mora 30 días vigente en todos los sectores (Estudio)

Políticas de la solicitud:
     R21 Nacionalidad diferente a colombiana (BRD)
     R22 Multas en el RUNT (BRD)
     E1  Cliente diferente a persona natural (tipo de documento NIT/PJE)

Exclusiones de score (Acierta / Advance):
     score 3      -> R1 fallecido
     score 0 ó 4  -> exclusión: no se asigna perfil de score; la
                     decisión depende del ingreso (E7 Estudio si
                     ingreso SMMLV >= Ingreso_E_2 / Ingreso_I_2, si no
                     RC3 Requiere codeudor). Se resuelve en el motor.

PENDIENTE DE CONFIRMAR CON EL MANUAL HDC+ DE LA VERSIÓN CONTRATADA: el
vector de comportamiento se lee asumiendo que el carácter 0 es el mes
más reciente (los primeros 12 caracteres = últimos 12 meses).
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from backend.models.buro_models import RespuestaHDC, TarjetaCredito
from backend.models.enums import (
    ESTADOS_DOCUMENTO_ACEPTADOS,
    TIPOS_ID_PERSONA_JURIDICA,
    Causal,
    EconomicSector,
)
from backend.models.motor_models import Solicitud
from backend.services.motor_parametros import MotorParametros
from backend.utils.fechas import calcular_edad

# Estados de pago HDC+ (Tabla 4 del manual):
# 45 = Cartera castigada; 47 = Dudoso recaudo; 03 = Pago total/cierre.
ESTADO_PAGO_CARTERA_CASTIGADA = "45"
ESTADO_PAGO_DUDOSO_RECAUDO = "47"
ESTADO_PAGO_PAGO_TOTAL = "03"
# Evento HDC+ 03 = Cancelación por mal manejo.
EVENTO_CANCELADA_MAL_MANEJO = "03"
# Estados de cuentas de ahorro/corriente:
# 06 = Embargada; 07 = Embargada activa.
PREFIJOS_EMBARGO = ("06", "07")
CALIFICACIONES_NEGATIVAS = {"C", "D", "E", "K"}
TOKENS_REESTRUCTURACION = ("REESTRUCT", "REFINANC", "RENEGOCI")
# Códigos especiales del score Experian: 0 y 4 = códigos de exclusión cuya
# salida se resuelve por ingreso (E7/RC3); 3 = persona reportada como fallecida.
CODIGOS_SCORE_EXCLUSION = {0, 4}
CODIGO_SCORE_FALLECIDO = 3


@dataclass
class CausalDisparada:
    causal: Causal
    detalle: str


@dataclass
class IndicadoresBuro:
    """Conteos derivados de HDC+ que alimentan las políticas de buró."""

    embargos: int = 0
    cancelaciones_mal_manejo: int = 0
    cartera_castigada: int = 0
    dudoso_recaudo: int = 0
    mora_60_vigente: int = 0
    moras_30_historicas: int = 0
    moras_60_historicas: int = 0
    moras_90_historicas: int = 0
    calificaciones_negativas: int = 0
    reestructuraciones: int = 0
    mora_30_vigente: int = 0
    estado_documento: str | None = None
    peor_calificacion: str | None = None

    @property
    def documento_vigente(self) -> bool:
        return not self.estado_documento or self.estado_documento in ESTADOS_DOCUMENTO_ACEPTADOS


@dataclass
class ResultadoExclusion:
    fallecido: bool = False
    codigo_exclusion: int | None = None  # 0 ó 4 cuando aplica
    ignorada: bool = False

    @property
    def es_exclusion(self) -> bool:
        return self.codigo_exclusion is not None and not self.fallecido and not self.ignorada


@dataclass
class ResultadoFiltros:
    causales: list[CausalDisparada] = field(default_factory=list)
    indicadores: IndicadoresBuro = field(default_factory=IndicadoresBuro)

    @property
    def aplica(self) -> bool:
        return bool(self.causales)

    @property
    def lista_causales(self) -> list[Causal]:
        return [c.causal for c in self.causales]

    @property
    def detalles(self) -> list[str]:
        return [c.detalle for c in self.causales]


# ---------------------------------------------------------------------------
# Helpers de interpretación del reporte
# ---------------------------------------------------------------------------
def _contar_moras_nivel(comportamiento: str | None, nivel: int, meses: int) -> int:
    """Cuenta un nivel exacto del vector: 1=30 días, 2=60 días."""
    return sum(1 for c in (comportamiento or "")[:meses] if c == str(nivel))


def _contar_moras_90_mas(comportamiento: str | None, meses: int) -> int:
    """Cuenta niveles numéricos 3-6 (90 días o más); D no es una mora numérica."""
    return sum(1 for c in (comportamiento or "")[:meses] if c.isdigit() and int(c) >= 3)


def _mora_vigente_numerica(comportamiento: str | None) -> int:
    """Devuelve la mora del período vigente (primer carácter); D/C/N no suman días."""
    if not comportamiento or not comportamiento[0].isdigit():
        return 0
    return int(comportamiento[0]) * 30


def _normalizar_codigo(valor) -> str:
    codigo = str(valor or "").strip().upper()
    return codigo.zfill(2) if codigo.isdigit() and len(codigo) == 1 else codigo


def es_codeudor(cuenta) -> bool:
    calidad = (cuenta.calidad_deudor or "").strip().upper()
    return calidad in {"01", "1"} or "CODEUDOR" in calidad


def _es_telcos(cuenta) -> bool:
    sector = str(cuenta.sector or "").strip().upper()
    return sector == EconomicSector.TELCOS.value or "TELCO" in sector or "TELECOM" in sector


def _aplica_sector(cuenta, params: MotorParametros, incluye_telcos: bool) -> bool:
    """Telcos solo cuenta en las reglas que la incluyen y con saldo en mora > Saldo_Mora_BE."""
    if not _es_telcos(cuenta):
        return True
    return incluye_telcos and cuenta.saldo_mora > params.saldo_mora_be


def _es_reestructurada(cuenta, params: MotorParametros) -> bool:
    descripcion = (cuenta.estado_origen_desc or "").upper()
    estado = (cuenta.estado_origen or "").upper()
    return estado in params.codigos_reestructuracion or any(
        token.upper() in descripcion for token in params.tokens_reestructuracion
    )


def _es_obligacion_cerrada(cuenta, params: MotorParametros) -> bool:
    estados_cerrados = {estado.upper() for estado in params.estados_buro_pago_total}
    if (cuenta.estado_pago or "").upper() in estados_cerrados or (
        cuenta.estado_origen or ""
    ).upper() in estados_cerrados:
        return True
    if isinstance(cuenta, TarjetaCredito) and (cuenta.evento_buro or "").strip() == "05":
        return True
    descripcion = " ".join(
        str(valor or "") for valor in (cuenta.estado_cuenta, cuenta.estado_cuenta_desc, cuenta.estado_origen_desc)
    ).upper()
    return any(token in descripcion for token in ("PAGO TOTAL", "PAGO VOL", "CANCELAD", "CERRAD", "INACTIV"))


def _tiene_calificacion_negativa(cuenta, params: MotorParametros, ventana: str) -> bool:
    negativas = {valor.upper() for valor in params.calificaciones_negativas}
    if _es_obligacion_cerrada(cuenta, params):
        return any(valor in negativas for valor in ventana.upper())
    return (cuenta.calificacion or "").strip().upper() in negativas


_ORDEN_CALIFICACION = {"A": 0, "AA": 0, "B": 1, "BB": 1, "C": 2, "CC": 2, "D": 3, "E": 4, "K": 5}


# ---------------------------------------------------------------------------
# 1. Derivación de indicadores desde HDC+
# ---------------------------------------------------------------------------
def derivar_indicadores_buro(
    hdc: RespuestaHDC,
    params: MotorParametros,
    fecha_evaluacion: date,
) -> IndicadoresBuro:
    ind = IndicadoresBuro()
    meses = params.meses_ventana_buro
    obligaciones = [*hdc.cuentas_cartera, *hdc.tarjetas_credito]

    for c in [*hdc.cuentas_ahorro, *hdc.cuentas_corriente]:
        if c.estado and c.estado.startswith(tuple(params.estados_buro_embargo)):
            ind.embargos += 1

    for c in obligaciones:
        vector = c.comportamiento or ""
        ventana = vector[:meses]
        fecha_corte = c.fecha_actualizacion or fecha_evaluacion
        fecha_inicio = fecha_corte - timedelta(days=365 * meses // 12)

        if (
            _normalizar_codigo(c.evento_buro) == _normalizar_codigo(params.evento_cancelacion_mal_manejo)
            and c.fecha_evento is not None
            and fecha_inicio <= c.fecha_evento <= fecha_corte
            and _aplica_sector(c, params, incluye_telcos=False)
        ):
            ind.cancelaciones_mal_manejo += 1

        if _aplica_sector(c, params, incluye_telcos=True):
            if c.estado_pago in params.estados_buro_cartera_castigada or "C" in ventana:
                ind.cartera_castigada += 1
            estados_dudoso = {_normalizar_codigo(estado) for estado in params.estados_buro_dudoso_recaudo}
            descripcion_estado = " ".join(
                str(valor or "") for valor in (c.estado_cuenta_desc, c.estado_origen_desc)
            ).upper()
            if (
                _normalizar_codigo(c.estado_pago) in estados_dudoso
                or "D" in ventana
                or "DUDOSO RECAUDO" in descripcion_estado
            ):
                ind.dudoso_recaudo += 1
            if (
                not c.bloqueada
                and c.estado_pago not in params.estados_buro_pago_total
                and _mora_vigente_numerica(vector) >= 60
            ):
                ind.mora_60_vigente += 1
            if not es_codeudor(c):
                ind.moras_30_historicas += _contar_moras_nivel(vector, 1, meses)
            ind.moras_60_historicas += _contar_moras_nivel(vector, 2, meses)
            ind.moras_90_historicas += _contar_moras_90_mas(vector, meses)

        # R10 aplica en todos los sectores; se excluyen únicamente codeudores.
        if not es_codeudor(c):
            calif = (c.calificacion or "").strip().upper()
            if _tiene_calificacion_negativa(c, params, ventana):
                ind.calificaciones_negativas += 1
            if calif in _ORDEN_CALIFICACION and (
                ind.peor_calificacion is None or _ORDEN_CALIFICACION[calif] > _ORDEN_CALIFICACION[ind.peor_calificacion]
            ):
                ind.peor_calificacion = calif

        if not es_codeudor(c) and _aplica_sector(c, params, incluye_telcos=False):
            if (
                _es_reestructurada(c, params)
                and c.fecha_estado_origen is not None
                and fecha_inicio <= c.fecha_estado_origen <= fecha_corte
            ):
                ind.reestructuraciones += 1

        # E2 - mora 30 vigente (todos los sectores; Telcos con saldo > Saldo_Mora_BE)
        if (
            not es_codeudor(c)
            and not c.bloqueada
            and c.estado_pago not in params.estados_buro_pago_total
            and not (_es_telcos(c) and c.saldo_mora <= params.saldo_mora_be)
            and _mora_vigente_numerica(vector) == 30
        ):
            ind.mora_30_vigente += 1

    if hdc.persona and hdc.persona.estado_documento not in (None, "", "None"):
        ind.estado_documento = hdc.persona.estado_documento

    return ind


# ---------------------------------------------------------------------------
# 2. Evaluación de políticas
# ---------------------------------------------------------------------------
def evaluar_politicas_buro(ind: IndicadoresBuro, params: MotorParametros) -> list[CausalDisparada]:
    c: list[CausalDisparada] = []
    if ind.embargos >= 1:
        c.append(CausalDisparada(Causal.R2, f"Embargos vigentes: {ind.embargos}"))
    if ind.cancelaciones_mal_manejo >= 1:
        c.append(CausalDisparada(Causal.R3, f"Cancelaciones negativas: {ind.cancelaciones_mal_manejo}"))
    if ind.cartera_castigada >= 1:
        c.append(CausalDisparada(Causal.R4, f"Cartera castigada: {ind.cartera_castigada}"))
    if ind.dudoso_recaudo >= 1:
        c.append(CausalDisparada(Causal.R5, f"Dudoso recaudo: {ind.dudoso_recaudo}"))
    if ind.mora_60_vigente >= 1:
        c.append(CausalDisparada(Causal.R6, f"Mora 60+ vigentes: {ind.mora_60_vigente}"))
    if ind.moras_30_historicas >= params.umbral_mora_30_historica:
        c.append(CausalDisparada(Causal.R7, f"Moras históricas 30d: {ind.moras_30_historicas}"))
    if ind.moras_60_historicas >= params.umbral_mora_60_historica:
        c.append(CausalDisparada(Causal.R8, f"Moras históricas 60d: {ind.moras_60_historicas}"))
    if ind.moras_90_historicas >= params.umbral_mora_90_historica:
        c.append(CausalDisparada(Causal.R9, f"Moras históricas 90d: {ind.moras_90_historicas}"))
    if ind.calificaciones_negativas >= 1:
        c.append(CausalDisparada(Causal.R10, f"Calificaciones negativas: {ind.calificaciones_negativas}"))
    if ind.reestructuraciones >= params.umbral_reestructuraciones:
        c.append(CausalDisparada(Causal.R11, f"Obligaciones reestructuradas: {ind.reestructuraciones}"))
    if not ind.documento_vigente:
        c.append(CausalDisparada(Causal.R12, f"Estado documento: {ind.estado_documento}"))
    if ind.mora_30_vigente >= 1:
        c.append(CausalDisparada(Causal.E2, f"Mora 30 días vigentes: {ind.mora_30_vigente}"))
    return c


def evaluar_politicas_solicitud(
    solicitud: Solicitud,
    params: MotorParametros,
    fecha_evaluacion: date,
) -> list[CausalDisparada]:
    c: list[CausalDisparada] = []
    if solicitud.tipo_id in TIPOS_ID_PERSONA_JURIDICA and params.activar_exclusion_persona_juridica:
        c.append(CausalDisparada(Causal.E1, f"Tipo de documento {solicitud.tipo_id.name}"))

    nacimiento = solicitud.fecha_nacimiento
    edad = calcular_edad(nacimiento, fecha_evaluacion)
    if edad < params.edad_minima_be or edad >= params.edad_maxima_be:
        c.append(
            CausalDisparada(
                Causal.R13, f"Edad {edad} fuera del rango [{params.edad_minima_be}, {params.edad_maxima_be})"
            )
        )

    nacionalidad = (solicitud.nacionalidad or "").strip().lower()
    if nacionalidad not in ("colombia", "colombiana", "colombiano", "co", "col"):
        c.append(CausalDisparada(Causal.R21, f"Nacionalidad: {solicitud.nacionalidad}"))

    if solicitud.tiene_multas_runt:
        c.append(CausalDisparada(Causal.R22, "Multas en el RUNT reportadas en la solicitud"))
    return c


def evaluar_exclusion_score(score: Decimal | None, params: MotorParametros | None = None) -> ResultadoExclusion:
    if score is None:
        return ResultadoExclusion()
    valor = int(score)
    if valor != score:  # 3.5 no es un código de exclusión
        return ResultadoExclusion()
    if valor == CODIGO_SCORE_FALLECIDO:
        ignorada = params is not None and not params.activar_exclusion_score_3_fallecido
        return ResultadoExclusion(fallecido=not ignorada, codigo_exclusion=valor, ignorada=ignorada)
    codigos_exclusion = params.scores_exclusion if params is not None else list(CODIGOS_SCORE_EXCLUSION)
    if valor in codigos_exclusion:
        activa = params is None or (
            params.activar_exclusion_score_0 if valor == 0 else params.activar_exclusion_score_4_codeudor
        )
        return ResultadoExclusion(codigo_exclusion=valor, ignorada=not activa)
    return ResultadoExclusion()


def evaluar_filtros_duros(
    hdc: RespuestaHDC,
    solicitud: Solicitud,
    params: MotorParametros,
    fecha_evaluacion: date,
    exclusion: ResultadoExclusion | None = None,
) -> ResultadoFiltros:
    """Todas las políticas previas al cálculo de ingreso, en orden BRD."""
    resultado = ResultadoFiltros()
    if exclusion and exclusion.fallecido:
        resultado.causales.append(CausalDisparada(Causal.R1, "Cliente reportado como fallecido (score 3)"))
    resultado.causales.extend(evaluar_politicas_solicitud(solicitud, params, fecha_evaluacion))
    resultado.indicadores = derivar_indicadores_buro(hdc, params, fecha_evaluacion)
    resultado.causales.extend(evaluar_politicas_buro(resultado.indicadores, params))
    return resultado
