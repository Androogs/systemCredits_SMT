"""Inicio de sesión de la plataforma."""

from fastapi import APIRouter

from backend.config import get_settings
from backend.models.auth_models import LoginRequest, LoginResponse
from backend.services.autenticacion_service import AutenticacionService

router = APIRouter(prefix="/auth", tags=["autenticacion"])


@router.post("/login", response_model=LoginResponse)
def iniciar_sesion(payload: LoginRequest) -> LoginResponse:
    usuario = AutenticacionService(get_settings()).autenticar(payload)
    return LoginResponse(usuario=usuario)
