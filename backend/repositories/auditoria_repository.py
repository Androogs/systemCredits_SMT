import json

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.db_models.auditoria_models import EvaluacionAuditoria
from backend.models.motor_models import ResultadoMotor
from backend.utils.fechas import calcular_edad


class AuditoriaRepository:
    """Registro y consulta de la auditoría de evaluaciones del motor."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def guardar(
        self,
        resultado: ResultadoMotor,
        origen_datos: str,
        id_solicitud: str | None = None,
    ) -> EvaluacionAuditoria:
        solicitud = resultado.solicitud
        registro = EvaluacionAuditoria(
            evaluacion_id=resultado.evaluacion_id,
            fecha_evaluacion=resultado.fecha_evaluacion,
            ambiente=resultado.ambiente,
            origen_datos=origen_datos,
            id_solicitud=id_solicitud,
            tipo_id=solicitud.tipo_id.value,
            numero_id=solicitud.numero_id,
            ocupacion=solicitud.ocupacion.value,
            edad=calcular_edad(solicitud.fecha_nacimiento, resultado.fecha_evaluacion.date()),
            decision=resultado.decision.value,
            decision_interna=resultado.decision_interna.value,
            causales=json.dumps([c.model_dump(mode="json") for c in resultado.causales_detalle], ensure_ascii=False),
            tiempo_ms=resultado.tiempo_ms,
            request_json=solicitud.model_dump_json(),
            # Sin respuestas completas del buró (datos personales de terceros).
            resultado_json=resultado.model_dump_json(exclude={"hdc_respuesta", "valor_ingreso_respuesta"}),
        )
        self.db.add(registro)
        self.db.flush()
        return registro

    def obtener(self, evaluacion_id: str) -> EvaluacionAuditoria | None:
        return self.db.execute(
            select(EvaluacionAuditoria).where(EvaluacionAuditoria.evaluacion_id == evaluacion_id)
        ).scalar_one_or_none()

    def listar(
        self,
        limite: int = 50,
        numero_id: str | None = None,
        decision: str | None = None,
        id_solicitud: str | None = None,
    ) -> list[EvaluacionAuditoria]:
        stmt = select(EvaluacionAuditoria).order_by(desc(EvaluacionAuditoria.fecha_evaluacion))
        if numero_id:
            stmt = stmt.where(EvaluacionAuditoria.numero_id == numero_id)
        if decision:
            stmt = stmt.where(EvaluacionAuditoria.decision == decision)
        if id_solicitud:
            stmt = stmt.where(EvaluacionAuditoria.id_solicitud == id_solicitud)
        return list(self.db.execute(stmt.limit(limite)).scalars().all())
