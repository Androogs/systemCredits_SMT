"""Esquemas de autenticación de la API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    correo: str = Field(min_length=3, max_length=254)
    contrasena: str = Field(min_length=1, max_length=256)


class ConcesionarioSesion(BaseModel):
    id_concesionario: int
    nombre: str
    # Ciudad de la sede: la muestra el formulario de asesores
    # (readonly — es un dato del concesionario, no de la persona).
    ciudad: str | None = None


class UsuarioAutenticado(BaseModel):
    correo: str
    nombre: str
    rol: str
    roles: list[str] = []
    # Sede del asesor (o la del primer concesionario del aliado):
    # alimenta las cabeceras del wizard y el alcance de consultas.
    concesionario: ConcesionarioSesion | None = None
    # True tras alta o restablecimiento admin: el guard del panel fuerza
    # el cambio de clave antes de operar.
    requiere_cambio_password: bool = False


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    usuario: UsuarioAutenticado


class RefreshRequest(BaseModel):
    """El refresh token opaco es la credencial: no va en el header
    Authorization (ese es el access JWT)."""

    refresh_token: str = Field(min_length=10, max_length=500)


class RefreshResponse(BaseModel):
    """Rotación: cada /refresh entrega un refresh nuevo y mata el viejo."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    usuario: UsuarioAutenticado


class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(default=None, max_length=500)


class SolicitarRecuperacionRequest(BaseModel):
    correo: str = Field(min_length=3, max_length=320)


class RestablecerClaveTokenRequest(BaseModel):
    """Restablecimiento con el token del correo (un solo uso)."""

    token: str = Field(min_length=10, max_length=500)
    contrasena_nueva: str = Field(min_length=8, max_length=128)


class MensajeGenerico(BaseModel):
    """Respuesta uniforme sin filtrar información (p. ej. si el correo
    existe o no — mismo mensaje para no enumerar cuentas)."""

    mensaje: str


class CambiarClaveRequest(BaseModel):
    """Self-service: el usuario autenticado prueba conocer su clave."""

    contrasena_actual: str = Field(min_length=1, max_length=256)
    contrasena_nueva: str = Field(min_length=8, max_length=128)


# ---------------------------------------------------------------------------
# Administración de usuarios (solo rol admin)
# ---------------------------------------------------------------------------


class AliadoOpcion(BaseModel):
    id_aliado: int
    nombre: str


class UsuarioGestionResponse(BaseModel):
    """Fila del listado de usuarios de la pantalla Ajustes."""

    id_usuario: UUID
    correo: str
    nombre: str | None
    estado: str
    roles: list[str]
    concesionario: ConcesionarioSesion | None = None
    # Id+nombre: la UI de edición precarga el vínculo por id.
    aliados: list[AliadoOpcion] = Field(default_factory=list)
    # Ficha del asesor (solo usuarios con rol asesor): la persona detrás
    # del correo corporativo permanente.
    cedula: str | None = None
    telefono: str | None = None
    requiere_cambio_password: bool
    fecha_ultimo_acceso: datetime | None = None
    bloqueado_hasta: datetime | None = None


class RolOpcion(BaseModel):
    id_rol: int
    nombre: str


class AsesorOpcion(BaseModel):
    """Fila del select de asesores (filtro del panel y formulario)."""

    id_asesor: int
    nombre: str
    id_concesionario: int | None = None


class OpcionesUsuarioResponse(BaseModel):
    """Catálogos de los selects del formulario de usuario."""

    roles: list[RolOpcion]
    concesionarios: list[ConcesionarioSesion]
    aliados: list[AliadoOpcion]
    asesores: list[AsesorOpcion] = Field(default_factory=list)


class CrearUsuarioRequest(BaseModel):
    correo: str = Field(min_length=3, max_length=320)
    nombre: str = Field(min_length=3, max_length=180)
    contrasena: str = Field(min_length=8, max_length=128)
    roles: list[str] = Field(min_length=1)
    # Vínculos opcionales según el rol: asesor → su sede; aliado → su
    # aliado financiero.
    id_concesionario: int | None = Field(default=None, ge=1)
    id_aliado: int | None = Field(default=None, ge=1)
    # Ficha del asesor: cédula y celular de la persona (obligatorios
    # cuando el rol es asesor — el correo es permanente, la persona
    # puede cambiar).
    cedula: str | None = Field(default=None, max_length=40)
    telefono: str | None = Field(default=None, max_length=40)


class ActualizarUsuarioRequest(BaseModel):
    """Campos editables; los ausentes no se tocan, los presentes con
    null/[] limpian el vínculo correspondiente."""

    nombre: str | None = Field(default=None, min_length=3, max_length=180)
    estado: str | None = Field(default=None)
    roles: list[str] | None = None
    id_concesionario: int | None = None
    id_aliado: int | None = None
    cedula: str | None = Field(default=None, max_length=40)
    telefono: str | None = Field(default=None, max_length=40)


class AsesorHistorialResponse(BaseModel):
    """Renglón del historial de la cuenta de asesor: quién cambió qué,
    cuándo y de qué valor a cuál."""

    fecha: datetime
    cambios: dict
    nombre_quien: str | None = None


class RestablecerClaveRequest(BaseModel):
    contrasena: str = Field(min_length=8, max_length=128)
