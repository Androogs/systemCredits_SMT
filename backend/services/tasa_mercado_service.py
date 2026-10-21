"""Tasa de mercado de referencia: TIBC de la SFC convertida a m.v.

Trae el Interés Bancario Corriente certificado por la Superintendencia
Financiera (dataset TIBC de datos.gov.co) para las modalidades de
consumo que aplican a un crédito de moto, convierte la tasa efectiva
anual a mensual vencida y expone la usura vigente. La modalidad se
elige por monto: "bajo monto" cubre créditos de hasta 6 SMMLV.

La consulta se cachea en memoria por `sfc_tasas_cache_segundos` y, si
la fuente falla con cache expirada, se sigue sirviendo la última
lectura conocida — la referencia es informativa, no bloquea el flujo.
"""

import time
from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from backend.config import Settings, get_settings
from backend.integrations.sfc.tasas_client import TasasSfcClient
from backend.services.motor_exceptions import DataCreditoError

MODALIDAD_BAJO_MONTO = "CONSUMO BAJO MONTO"
MODALIDAD_ORDINARIO = "CONSUMO Y ORDINARIO"
# La SFC clasifica como "consumo de bajo monto" los créditos de hasta
# 6 SMMLV; por encima aplica la modalidad consumo y ordinario.
SMMLV_UMBRAL_BAJO_MONTO = 6
FACTOR_USURA = 1.5
FUENTE = "Superintendencia Financiera · datos.gov.co (TIBC)"


class ClienteTasas(Protocol):
    def tasas_vigentes(self, modalidades: Sequence[str]) -> list[dict[str, Any]]: ...


def ea_a_mv(tasa_ea: float) -> float:
    """Convierte % efectivo anual a % nominal mensual vencido."""
    return ((1 + tasa_ea / 100) ** (1 / 12) - 1) * 100


def modalidad_por_monto(monto: float | None, smmlv: int) -> str:
    """Modalidad TIBC que aplica al monto financiado (6 SMMLV de tope)."""
    if monto is None or monto <= SMMLV_UMBRAL_BAJO_MONTO * smmlv:
        return MODALIDAD_BAJO_MONTO
    return MODALIDAD_ORDINARIO


@dataclass(frozen=True)
class ModalidadTasa:
    modalidad: str
    tasa_ea: float
    tasa_mv: float
    usura_ea: float
    usura_mv: float
    vigencia_desde: str
    vigencia_hasta: str
    resolucion: str


@dataclass(frozen=True)
class TasasMercado:
    umbral_bajo_monto: int
    fuente: str
    bajo_monto: ModalidadTasa
    ordinario: ModalidadTasa

    def modalidad_para(self, monto: float | None, smmlv: int) -> ModalidadTasa:
        if modalidad_por_monto(monto, smmlv) == MODALIDAD_BAJO_MONTO:
            return self.bajo_monto
        return self.ordinario


def _porcentaje(valor: Any) -> float:
    """'44.44%' -> 44.44; tolera número plano o con decimales."""
    texto = str(valor or "").strip().rstrip("%").replace(",", ".")
    return float(texto) if texto else 0.0


def _fila_a_modalidad(fila: dict[str, Any]) -> ModalidadTasa:
    tasa_ea = _porcentaje(fila.get("interes_bancario_corriente"))
    usura_ea = round(tasa_ea * FACTOR_USURA, 2)
    return ModalidadTasa(
        modalidad=str(fila.get("modalidad") or ""),
        tasa_ea=tasa_ea,
        tasa_mv=round(ea_a_mv(tasa_ea), 4),
        usura_ea=usura_ea,
        usura_mv=round(ea_a_mv(usura_ea), 4),
        vigencia_desde=str(fila.get("vigencia_desde") or "")[:10],
        vigencia_hasta=str(fila.get("vigencia_hasta") or "")[:10],
        resolucion=str(fila.get("resolucion") or ""),
    )


class TasaMercadoService:
    """Consulta cacheada del TIBC con degradado sobre la última lectura."""

    def __init__(self, cliente: ClienteTasas, settings: Settings):
        self.cliente = cliente
        self.settings = settings
        # (timestamp monotónico de expiración, datos) — in-proceso, como
        # el resto del cacheado del sistema a esta escala (ver D94).
        self._cache: tuple[float, TasasMercado] | None = None

    def tasas(self) -> TasasMercado:
        ahora = time.monotonic()
        if self._cache is not None and self._cache[0] > ahora:
            return self._cache[1]
        try:
            filas = self.cliente.tasas_vigentes(
                [MODALIDAD_BAJO_MONTO, MODALIDAD_ORDINARIO]
            )
        except DataCreditoError:
            if self._cache is not None:
                return self._cache[1]
            raise
        datos = self._armar(filas)
        self._cache = (ahora + self.settings.sfc_tasas_cache_segundos, datos)
        return datos

    def _armar(self, filas: list[dict[str, Any]]) -> TasasMercado:
        por_modalidad: dict[str, ModalidadTasa] = {}
        for fila in filas:
            modalidad = _fila_a_modalidad(fila)
            if (
                modalidad.modalidad
                in (MODALIDAD_BAJO_MONTO, MODALIDAD_ORDINARIO)
                and modalidad.modalidad not in por_modalidad
            ):
                por_modalidad[modalidad.modalidad] = modalidad
        faltantes = {
            MODALIDAD_BAJO_MONTO,
            MODALIDAD_ORDINARIO,
        } - por_modalidad.keys()
        if faltantes:
            raise DataCreditoError(
                "sfc_tasas", 200, f"Modalidades ausentes: {sorted(faltantes)}"
            )
        return TasasMercado(
            umbral_bajo_monto=SMMLV_UMBRAL_BAJO_MONTO * self.settings.smmlv,
            fuente=FUENTE,
            bajo_monto=por_modalidad[MODALIDAD_BAJO_MONTO],
            ordinario=por_modalidad[MODALIDAD_ORDINARIO],
        )


def crear_servicio_tasa_mercado(
    settings: Settings | None = None,
) -> TasaMercadoService:
    settings = settings or get_settings()
    return TasaMercadoService(TasasSfcClient(settings), settings)
