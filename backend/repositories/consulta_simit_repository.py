"""Persistencia del resultado SIMIT por persona (tabla consulta_simit).

El proveedor "portal" es gratis pero frágil y visible para la FCM:
guardar el resultado por documento (SIMIT_CACHE_DIAS) evita repetir la
consulta por cada re-evaluación o retoma, acota la carga sobre el
portal y deja la traza de qué respondió el SIMIT en cada evaluación.
La llave es la persona (tipo_id + numero_id), como en consulta_runt y
consulta_buro.
"""

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.db_models.auditoria_models import ConsultaSimit
from backend.integrations.simit.client import (
    ResultadoSimit,
    resultado_a_json,
    resultado_desde_crudo,
)


class ConsultaSimitRepository:
    def __init__(self, db: Session):
        self.db = db

    def ultima_vigente(
        self, tipo_id: str, numero_id: str, dias: int
    ) -> ConsultaSimit | None:
        """Último resultado SIMIT dentro del período de vigencia."""
        corte = datetime.now(UTC) - timedelta(days=dias)
        return self.db.execute(
            select(ConsultaSimit)
            .where(
                ConsultaSimit.tipo_id == tipo_id,
                ConsultaSimit.numero_id == numero_id,
                ConsultaSimit.fecha_consulta >= corte,
            )
            .order_by(desc(ConsultaSimit.fecha_consulta))
            .limit(1)
        ).scalar_one_or_none()

    def registrar(
        self,
        tipo_id: str,
        numero_id: str,
        id_solicitud: UUID | str | None,
        resultado: ResultadoSimit,
    ) -> ConsultaSimit:
        fila = ConsultaSimit(
            tipo_id=tipo_id,
            numero_id=numero_id,
            id_solicitud=str(id_solicitud) if id_solicitud else None,
            origen=resultado.origen,
            resultado_json=json.dumps(resultado_a_json(resultado), default=str),
        )
        self.db.add(fila)
        self.db.flush()
        return fila

    @staticmethod
    def a_resultado(fila: ConsultaSimit) -> ResultadoSimit:
        return resultado_desde_crudo(json.loads(fila.resultado_json))
