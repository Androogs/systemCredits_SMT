"""Modelos de identidad y acceso: usuario, rol, asesor, aliado y auditoría.

Espejo de las tablas de `schema.sql` que el ORM aún no mapeaba (se
sembraban por `insert.sql` en Postgres y por `_SQLITE_SCHEMA_EXTRA` en
SQLite). Convención del proyecto: los tipos ENUM/CITEXT/INET de Postgres
se mapean como `Enum(create_type=False)`/`String` para que SQLite
levante el mismo esquema en pruebas.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    JSON,
    Numeric,
    SmallInteger,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from backend.db_models.base import Base

ROL_USUARIO_DB = Enum(
    "cliente", "asesor", "aliado", "admin", "contabilidad", "concesionario",
    name="rol_usuario", create_type=False,
)
ESTADO_USUARIO_DB = Enum(
    "pendiente_verificacion", "activo", "bloqueado", "inactivo",
    name="estado_usuario", create_type=False,
)


def _ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


class Rol(Base):
    __tablename__ = "rol"

    # SMALLINT en Postgres; Integer aquí porque SQLite solo autoincrementa
    # INTEGER PRIMARY KEY (la DDL de Postgres ya existe vía schema.sql).
    id_rol: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(ROL_USUARIO_DB, unique=True)
    descripcion: Mapped[str | None] = mapped_column(String(200))


class Usuario(Base):
    __tablename__ = "usuario"

    id_usuario: Mapped[object] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    # CITEXT en Postgres; String + comparación case-insensitive en el
    # repositorio para que SQLite se comporte igual.
    correo: Mapped[str] = mapped_column(String(320), unique=True)
    hash_contrasena: Mapped[str] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(
        ESTADO_USUARIO_DB,
        default="pendiente_verificacion",
        server_default="pendiente_verificacion",
    )
    nombre_completo: Mapped[str | None] = mapped_column(String(180))
    fecha_verificacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fecha_ultimo_acceso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fecha_ultimo_cambio_password: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requiere_cambio_password: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    intentos_fallidos_login: Mapped[int] = mapped_column(
        SmallInteger, default=0, server_default="0"
    )
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_ahora_utc, server_default=func.now()
    )
    fecha_actualizacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_ahora_utc,
        onupdate=_ahora_utc,
        server_default=func.now(),
    )


class UsuarioRol(Base):
    __tablename__ = "usuario_rol"

    id_usuario: Mapped[object] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("usuario.id_usuario"), primary_key=True
    )
    id_rol: Mapped[int] = mapped_column(ForeignKey("rol.id_rol"), primary_key=True)
    fecha_asignacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_ahora_utc, server_default=func.now()
    )


class Asesor(Base):
    __tablename__ = "asesor"

    id_asesor: Mapped[int] = mapped_column(primary_key=True)
    id_usuario: Mapped[object] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("usuario.id_usuario"), unique=True
    )
    nombre: Mapped[str] = mapped_column(String(180))
    telefono: Mapped[str | None] = mapped_column(String(40))
    # Cédula de la persona que radica (no del cliente): identidad real
    # detrás de la cuenta. El correo corporativo es permanente, pero la
    # persona puede cambiar — las solicitudes quedan ligadas a esta
    # cédula para que cada radicación se atribuya a quien la hizo.
    num_cedula: Mapped[str | None] = mapped_column(String(40))
    # Desde cuándo la persona actual maneja la cuenta: se actualiza
    # cuando cambia el titular (cédula entre valores distintos, o
    # cédula nueva junto con nombre nuevo). Las solicitudes legadas
    # sin foto de cédula solo las ve quien estaba al crearlas.
    persona_desde: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    id_ciudad: Mapped[int | None] = mapped_column(ForeignKey("ciudad.id_ciudad"))
    # Sede del asesor: habilita el alcance "solicitudes de su
    # concesionario". Nuevo en 0014 (no existía en el DDL original).
    id_concesionario: Mapped[int | None] = mapped_column(
        ForeignKey("concesionario.id_concesionario")
    )


class Concesionario(Base):
    __tablename__ = "concesionario"

    id_concesionario: Mapped[int] = mapped_column(primary_key=True)
    nit: Mapped[str | None] = mapped_column(String(30), unique=True)
    nombre: Mapped[str] = mapped_column(String(180), unique=True)
    id_ciudad: Mapped[int | None] = mapped_column(ForeignKey("ciudad.id_ciudad"))


class AliadoUsuario(Base):
    __tablename__ = "aliado_usuario"

    id_usuario: Mapped[object] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("usuario.id_usuario"), primary_key=True
    )
    id_aliado: Mapped[int] = mapped_column(
        ForeignKey("aliado_financiero.id_aliado"), primary_key=True
    )
    rol_interno: Mapped[str | None] = mapped_column(String(40))
    fecha_asignacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_ahora_utc, server_default=func.now()
    )


class AliadoConcesionario(Base):
    __tablename__ = "aliado_concesionario"

    id_aliado: Mapped[int] = mapped_column(
        ForeignKey("aliado_financiero.id_aliado"), primary_key=True
    )
    id_concesionario: Mapped[int] = mapped_column(
        ForeignKey("concesionario.id_concesionario"), primary_key=True
    )
    comision_pct: Mapped[float | None] = mapped_column(Numeric(8, 4))
    activo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    fecha_inicio: Mapped[object | None] = mapped_column(DateTime)
    fecha_fin: Mapped[object | None] = mapped_column(DateTime)


class RefreshToken(Base):
    """Refresh token opaco persistido: solo el hash (sha256) se guarda,
    el token plano solo viaja al cliente una vez. La rotación encadena
    cada token con el que lo reemplaza (`reemplazado_por`), y revocar
    apaga la sesión en servidor — un access JWT sigue vivo hasta su exp,
    pero ya no se puede renovar."""

    __tablename__ = "refresh_token"

    id_refresh: Mapped[int] = mapped_column(primary_key=True)
    id_usuario: Mapped[object] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("usuario.id_usuario"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revocado: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    ip: Mapped[str | None] = mapped_column(
        INET().with_variant(String(45), "sqlite")
    )
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_ahora_utc, server_default=func.now()
    )
    fecha_revocacion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    reemplazado_por: Mapped[int | None] = mapped_column(
        ForeignKey("refresh_token.id_refresh")
    )


class TokenRecuperacion(Base):
    """Token de un solo uso para "olvidé mi clave": se guarda el hash,
    expira en `recuperacion_token_minutos` y queda marcado al usarse."""

    __tablename__ = "token_recuperacion"

    id_token: Mapped[int] = mapped_column(primary_key=True)
    id_usuario: Mapped[object] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("usuario.id_usuario"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), index=True)
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    usado: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    ip: Mapped[str | None] = mapped_column(
        INET().with_variant(String(45), "sqlite")
    )
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_ahora_utc, server_default=func.now()
    )
    fecha_uso: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )


class AsesorHistorial(Base):
    """Historial de cambios de la ficha del asesor: la cuenta (correo
    corporativo) es permanente, pero la persona puede cambiar — cada
    edición deja un renglón con el valor anterior y el nuevo, más quién
    lo hizo. Alimenta la pestaña "Historial" de la ficha en Ajustes."""

    __tablename__ = "asesor_historial"

    id_historial: Mapped[int] = mapped_column(primary_key=True)
    id_asesor: Mapped[int] = mapped_column(
        ForeignKey("asesor.id_asesor"), index=True
    )
    # Quién ejecutó el cambio (admin o concesionario de la sede).
    id_usuario_cambio: Mapped[object] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("usuario.id_usuario")
    )
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_ahora_utc
    )
    # {campo: {"antes": ..., "despues": ...}} — solo los campos que
    # efectivamente cambiaron (nombre, cedula, telefono, sede, estado).
    cambios: Mapped[dict] = mapped_column(JSON)


class ConcesionarioUsuario(Base):
    """Vínculo usuario ↔ sede para el rol `concesionario` (administrador
    de sede): un usuario administra a lo sumo una sede; una sede puede
    tener varios administradores. No reutiliza `asesor` para no
    contaminar el catálogo de radicadores (filtros del panel/aliado)."""

    __tablename__ = "concesionario_usuario"

    id_usuario: Mapped[object] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("usuario.id_usuario"), primary_key=True
    )
    id_concesionario: Mapped[int] = mapped_column(
        ForeignKey("concesionario.id_concesionario"), nullable=False
    )


class AuditoriaUsuario(Base):
    __tablename__ = "auditoria_usuario"

    id_auditoria: Mapped[int] = mapped_column(primary_key=True)
    id_usuario: Mapped[object | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("usuario.id_usuario")
    )
    accion: Mapped[str] = mapped_column(String(100))
    descripcion: Mapped[str | None] = mapped_column(Text)
    # INET en Postgres; VARCHAR en SQLite (misma convención que
    # otp.ip_solicitud en models.py). Un String plano renderiza
    # ::VARCHAR en el INSERT y Postgres rechaza inet = varchar.
    ip: Mapped[str | None] = mapped_column(
        INET().with_variant(String(45), "sqlite")
    )
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_ahora_utc, server_default=func.now()
    )
