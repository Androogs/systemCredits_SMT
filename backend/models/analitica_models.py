"""Respuesta del panel de analítica (efectividad y perfil para campañas).

Solo lectura agregada; no expone PII del cliente más allá del nombre y
cédula del asesor radicador (dato ya visible en el expediente admin).
"""

from datetime import date, datetime

from pydantic import BaseModel


class FilaEfectividad(BaseModel):
    """Una sede o ciudad: radicaciones y su conversión a crédito."""

    nombre: str
    radicadas: int
    aprobadas: int
    efectividad: float
    creditos: int
    rechazadas: int
    saldo_aprobado: float


class FilaAsesor(BaseModel):
    asesor: str
    cedula: str | None = None
    radicadas: int
    creditos: int
    efectividad: float
    aprobadas: int
    formalizadas: int
    saldo_aprobado: float


class PerfilSede(BaseModel):
    nombre: str
    radicadas: int
    edad_promedio: float | None
    # Distribución de la evaluación vigente; 'sin_evaluar' cubre las
    # solicitudes sin evaluación (abandonos, canceladas tempranas).
    score: dict[str, int]
    ingreso: dict[str, int]
    ocupacion: dict[str, int]


class CausalTotal(BaseModel):
    codigo: str
    descripcion: str
    total: int


class CausalSede(BaseModel):
    nombre: str
    rechazadas: int
    causales: list[CausalTotal]


class Segmento(BaseModel):
    segmento: str
    radicadas: int
    aprobadas: int
    creditos: int


class DimensionSegmentos(BaseModel):
    dimension: str
    segmentos: list[Segmento]


class AnaliticaResponse(BaseModel):
    generado_en: datetime
    desde: date | None
    hasta: date | None
    # True cuando el panel muestra todo el histórico (sin rango).
    historico_completo: bool
    total_radicadas: int
    por_sede: list[FilaEfectividad]
    por_marca: list[FilaEfectividad]
    por_asesor: list[FilaAsesor]
    perfil_por_sede: list[PerfilSede]
    causales_por_sede: list[CausalSede]
    segmentos: list[DimensionSegmentos]
