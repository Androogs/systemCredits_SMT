"""Sesiones de captura remota y evidencias documentales.

La sesión de captura existe antes que la solicitud (el paso 3 del wizard
antecede a la creación en el paso 7): el token público permite al cliente
subir cédula y video desde su celular sin autenticarse, y la sesión se
enlaza a la solicitud cuando esta se crea.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db_models.base import Base
from backend.db_models.models import _ahora_utc


class SesionCaptura(Base):
    __tablename__ = "sesion_captura"

    id_sesion: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    estado: Mapped[str] = mapped_column(String(20), default="pendiente", index=True)  # pendiente|completada|expirada
    id_solicitud: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("solicitud_credito.id_solicitud"), index=True
    )
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora_utc)

    evidencias: Mapped[list["DocumentoEvidencia"]] = relationship(
        back_populates="sesion", cascade="all, delete-orphan"
    )


class DocumentoEvidencia(Base):
    __tablename__ = "documento_evidencia"

    id_evidencia: Mapped[int] = mapped_column(primary_key=True)
    id_sesion: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sesion_captura.id_sesion"), index=True
    )
    id_solicitud: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), index=True)
    tipo: Mapped[str] = mapped_column(String(20))  # cedula_frontal | cedula_reverso | video_prueba_vida
    ruta: Mapped[str] = mapped_column(String(255))
    nombre_original: Mapped[str | None] = mapped_column(String(255))
    mime: Mapped[str] = mapped_column(String(60))
    tamano_bytes: Mapped[int] = mapped_column(BigInteger)
    hash_sha256: Mapped[str] = mapped_column(String(64))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora_utc)

    sesion: Mapped[SesionCaptura] = relationship(back_populates="evidencias")
