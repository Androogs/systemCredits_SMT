"""
Tabla de auditoría del motor: una fila por evaluación, con la
solicitud y el resultado (sin las respuestas completas del buró, que
contienen datos personales de terceros).
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Integer, String, Text, Uuid
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
    # Huella sha256 corta del juego de parámetros vigente en la evaluación.
    parametros_huella: Mapped[str | None] = mapped_column(String(16))
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


class ConsultaBuro(Base):
    """Reporte crudo de centrales por persona: la consulta a Experian se
    paga una vez y el reporte se reutiliza mientras esté vigente
    (BURO_CACHE_DIAS). Guarda la respuesta completa — a diferencia de
    resultado_json, que solo conserva el detalle normalizado — porque
    rehidratarla permite correr el motor de nuevo sin otra consulta.
    Cada fila documenta con qué datos de centrales se evaluó y cuándo se
    consultaron; la vigencia acota también la retención de datos
    personales de terceros."""

    __tablename__ = "consulta_buro"

    id_consulta: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tipo_id: Mapped[str] = mapped_column(String(2))
    numero_id: Mapped[str] = mapped_column(String(20), index=True)
    # En Postgres es UUID REFERENCES solicitud_credito; en SQLite queda CHAR(32).
    id_solicitud: Mapped[UUID | None] = mapped_column(Uuid, index=True)
    fecha_consulta: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora_utc, index=True)
    origen: Mapped[str] = mapped_column(String(30))  # experian
    hdc_json: Mapped[str] = mapped_column(Text)
    valor_ingreso_json: Mapped[str | None] = mapped_column(Text)

    def a_reportes(self) -> tuple["RespuestaHDC", "RespuestaValorIngreso | None"]:
        from backend.models.buro_models import RespuestaHDC, RespuestaValorIngreso

        hdc = RespuestaHDC.model_validate_json(self.hdc_json)
        vi = RespuestaValorIngreso.model_validate_json(self.valor_ingreso_json) if self.valor_ingreso_json else None
        return hdc, vi


class ConsultaSimit(Base):
    """Resultado del estado de cuenta de tránsito SIMIT por persona.

    El proveedor "portal" (API interna del portal ciudadano FCM) es
    gratis pero frágil (PoW captcha, cambios del portal, límites por
    IP): guardar el resultado por documento durante SIMIT_CACHE_DIAS
    acota la carga sobre el portal y deja trazado qué respondió el
    SIMIT en cada evaluación. La consulta en background al aceptar el
    Habeas Data también escribe aquí: la evaluación posterior reusa la
    fila vigente en vez de pegarle al portal en caliente.
    """

    __tablename__ = "consulta_simit"

    id_consulta: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tipo_id: Mapped[str] = mapped_column(String(2))
    numero_id: Mapped[str] = mapped_column(String(20), index=True)
    id_solicitud: Mapped[str | None] = mapped_column(String(36), index=True)
    fecha_consulta: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora_utc, index=True)
    origen: Mapped[str] = mapped_column(String(30))  # portal | placapi | mock:<esc> | declarado en la solicitud
    resultado_json: Mapped[str] = mapped_column(Text)
