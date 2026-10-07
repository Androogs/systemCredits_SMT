"""
Tabla de auditoría del motor: una fila por evaluación, con la
solicitud y el resultado (sin las respuestas completas del buró, que
contienen datos personales de terceros).
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db_models.base import Base
from backend.db_models.models import _ahora_utc


class EvaluacionAuditoria(Base):
    __tablename__ = "motor_evaluacion_auditoria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evaluacion_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    fecha_evaluacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora_utc, index=True)
    ambiente: Mapped[str] = mapped_column(String(20))
    origen_datos: Mapped[str] = mapped_column(String(40))  # mock:<escenario> | experian | archivos | cotizantes
    id_solicitud: Mapped[str | None] = mapped_column(String(36), index=True)
    tipo_id: Mapped[str] = mapped_column(String(2))
    numero_id: Mapped[str] = mapped_column(String(20), index=True)
    ocupacion: Mapped[str] = mapped_column(String(30))
    edad: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String(20), index=True)
    decision_interna: Mapped[str] = mapped_column(String(30))
    causales: Mapped[str] = mapped_column(Text)  # JSON [{codigo, descripcion, tipo}]
    tiempo_ms: Mapped[int] = mapped_column(Integer, default=0)
    request_json: Mapped[str] = mapped_column(Text)
    resultado_json: Mapped[str] = mapped_column(Text)
