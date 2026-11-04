"""Persistencia del reporte crudo de centrales (tabla consulta_buro).

La consulta a Experian es un recurso pago por persona: si ya hay un
reporte vigente (BURO_CACHE_DIAS) la re-evaluación corre el motor con
esos datos en vez de consumir otra llamada. La llave es la persona
(tipo_id + numero_id): el reporte es reutilizable entre solicitudes y
entre retomas mientras no venza.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.db_models.auditoria_models import ConsultaBuro
from backend.models.buro_models import RespuestaHDC, RespuestaValorIngreso


class ConsultaBuroRepository:
    def __init__(self, db: Session):
        self.db = db

    def ultima_vigente(
        self, tipo_id: str, numero_id: str, dias: int
    ) -> ConsultaBuro | None:
        """Último reporte consultado dentro del período de vigencia."""
        corte = datetime.now(UTC) - timedelta(days=dias)
        return self.db.execute(
            select(ConsultaBuro)
            .where(
                ConsultaBuro.tipo_id == tipo_id,
                ConsultaBuro.numero_id == numero_id,
                ConsultaBuro.fecha_consulta >= corte,
            )
            .order_by(desc(ConsultaBuro.fecha_consulta))
            .limit(1)
        ).scalar_one_or_none()

    def registrar(
        self,
        tipo_id: str,
        numero_id: str,
        id_solicitud: UUID | str | None,
        hdc: RespuestaHDC,
        valor_ingreso: RespuestaValorIngreso | None,
        origen: str = "experian",
    ) -> ConsultaBuro:
        fila = ConsultaBuro(
            tipo_id=tipo_id,
            numero_id=numero_id,
            id_solicitud=UUID(str(id_solicitud)) if id_solicitud else None,
            origen=origen,
            hdc_json=hdc.model_dump_json(),
            valor_ingreso_json=valor_ingreso.model_dump_json() if valor_ingreso else None,
        )
        self.db.add(fila)
        self.db.flush()
        return fila
