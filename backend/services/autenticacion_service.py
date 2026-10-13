"""Validación de credenciales de acceso para la plataforma."""

from hmac import compare_digest

from fastapi import HTTPException, status

from backend.config import Settings
from backend.models.auth_models import LoginRequest, UsuarioAutenticado


class AutenticacionService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def autenticar(self, payload: LoginRequest) -> UsuarioAutenticado:
        if self.settings.environment != "demo":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="El acceso de usuarios aún no está habilitado en este entorno.",
            )

        correo_valido = compare_digest(
            payload.correo.strip().casefold(),
            self.settings.demo_user_email.strip().casefold(),
        )
        contrasena_valida = compare_digest(
            payload.contrasena,
            self.settings.demo_user_password,
        )
        if not (correo_valido and contrasena_valida):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Correo o contraseña incorrectos.",
            )

        return UsuarioAutenticado(
            correo=self.settings.demo_user_email,
            nombre="Usuario de demostración",
            rol="Administrador",
        )
