"""Inicio de sesión, sesiones persistidas y recuperación de clave."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from backend.auth.dependencies import UsuarioActual, usuario_actual
from backend.config import get_settings
from backend.db_models.session import get_db
from backend.models.auth_models import (
    CambiarClaveRequest,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    MensajeGenerico,
    RefreshRequest,
    RefreshResponse,
    RestablecerClaveTokenRequest,
    SolicitarRecuperacionRequest,
    UsuarioAutenticado,
)
from backend.services.autenticacion_service import AutenticacionService

router = APIRouter(prefix="/auth", tags=["autenticacion"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/login", response_model=LoginResponse)
def iniciar_sesion(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> LoginResponse:
    usuario, token, refresh = AutenticacionService(
        db, get_settings()
    ).autenticar(payload, ip=_ip(request))
    return LoginResponse(
        access_token=token, refresh_token=refresh, usuario=usuario
    )


@router.post("/refresh", response_model=RefreshResponse)
def refrescar_sesion(
    payload: RefreshRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> RefreshResponse:
    """Renueva el access JWT rotando el refresh token: el usado queda
    revocado y encadenado al nuevo (reuso de uno viejo → 401)."""
    usuario, access, refresh = AutenticacionService(
        db, get_settings()
    ).refrescar(payload.refresh_token, ip=_ip(request))
    return RefreshResponse(
        access_token=access, refresh_token=refresh, usuario=usuario
    )


@router.post("/logout", response_model=MensajeGenerico)
def cerrar_sesion(
    payload: LogoutRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> MensajeGenerico:
    """Revoca el refresh token: la sesión ya no se puede renovar.
    Idempotente — el cliente puede llamarlo sin token válido."""
    AutenticacionService(db, get_settings()).cerrar_sesion(
        payload.refresh_token, ip=_ip(request)
    )
    return MensajeGenerico(mensaje="Sesión cerrada.")


@router.post("/cambiar-clave", response_model=UsuarioAutenticado)
def cambiar_clave(
    payload: CambiarClaveRequest,
    usuario: UsuarioActual = Depends(usuario_actual),
    db: Session = Depends(get_db),
) -> UsuarioAutenticado:
    """Cambio de clave propio (cualquier rol): resuelve la clave
    temporal que el admin entrega al crear o restablecer usuarios."""
    return AutenticacionService(db, get_settings()).cambiar_clave(
        usuario.id_usuario, payload
    )


@router.post("/recuperar-clave", response_model=MensajeGenerico)
def solicitar_recuperacion(
    payload: SolicitarRecuperacionRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> MensajeGenerico:
    """Flujo "olvidé mi clave": si el correo existe y está activo se
    envía un enlace con token de un solo uso. La respuesta es la misma
    para correos inexistentes (no se enumeran cuentas)."""
    AutenticacionService(db, get_settings()).solicitar_recuperacion(
        payload.correo, ip=_ip(request)
    )
    return MensajeGenerico(
        mensaje=(
            "Si el correo está registrado recibirás un enlace para "
            "restablecer tu contraseña."
        )
    )


@router.post("/restablecer-clave", response_model=MensajeGenerico)
def restablecer_clave(
    payload: RestablecerClaveTokenRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> MensajeGenerico:
    """Aplica la nueva clave con el token del correo. Token usado,
    vencido o inexistente → 400; al aplicar se cierran las sesiones."""
    AutenticacionService(db, get_settings()).restablecer_clave(
        payload, ip=_ip(request)
    )
    return MensajeGenerico(
        mensaje="Contraseña restablecida. Ya puedes iniciar sesión."
    )
