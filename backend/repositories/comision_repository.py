"""Consulta del reporte de comisiones: desembolsos confirmados del
radicador con su crédito y su cliente."""

from sqlalchemy.orm import Session

from backend.db_models.auth_models import Asesor
from backend.db_models.models import (
    Cliente,
    CreditoFinanciacion,
    Desembolso,
    SolicitudCredito,
)


class ComisionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def desembolsos(
        self, predicado_radicador=None
    ) -> list[
        tuple[Desembolso, CreditoFinanciacion, SolicitudCredito, Cliente, str]
    ]:
        """Desembolsos confirmados con su crédito, solicitud, cliente y
        nombre del radicador. `predicado_radicador` es el alcance por
        persona del asesor; None = sin filtro (vista del admin)."""
        q = (
            self.db.query(
                Desembolso,
                CreditoFinanciacion,
                SolicitudCredito,
                Cliente,
                Asesor.nombre.label("nombre_asesor"),
            )
            .join(
                CreditoFinanciacion,
                Desembolso.id_credito == CreditoFinanciacion.id_credito,
            )
            .join(
                SolicitudCredito,
                CreditoFinanciacion.id_solicitud
                == SolicitudCredito.id_solicitud,
            )
            .join(Cliente, SolicitudCredito.id_cliente == Cliente.id_cliente)
            .outerjoin(
                Asesor, SolicitudCredito.id_asesor == Asesor.id_asesor
            )
            .filter(Desembolso.estado == "confirmado")
        )
        if predicado_radicador is not None:
            q = q.filter(predicado_radicador)
        return q.order_by(
            Desembolso.fecha_desembolso.desc(),
            Desembolso.id_desembolso.desc(),
        ).all()
