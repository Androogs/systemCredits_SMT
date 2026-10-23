"""Emisión y verificación de los JWT de sesión de la plataforma.

HS256 con secreto de entorno (`JWT_SECRETO`); la vigencia default es la
jornada laboral (8h). Fuera del entorno demo el secreto es obligatorio:
sin él no se emiten tokens.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import PyJWTError

from backend.config import Settings


class JwtService:
    def __init__(self, settings: Settings):
        self._settings = settings

    def secreto_configurado(self) -> bool:
        return bool(self._settings.jwt_secreto_efectivo())

    def emitir(
        self,
        *,
        id_usuario: uuid.UUID,
        nombre: str,
        roles: list[str],
    ) -> str:
        ahora = datetime.now(timezone.utc)
        claims = {
            "sub": str(id_usuario),
            "nombre": nombre,
            "roles": roles,
            "iat": int(ahora.timestamp()),
            "exp": int(
                (ahora + timedelta(hours=self._settings.jwt_ttl_horas)).timestamp()
            ),
        }
        return jwt.encode(
            claims, self._settings.jwt_secreto_efectivo(), algorithm="HS256"
        )

    def decodificar(self, token: str) -> dict | None:
        """Devuelve los claims del token o None si es inválido/expiró."""
        try:
            return jwt.decode(
                token,
                self._settings.jwt_secreto_efectivo(),
                algorithms=["HS256"],
            )
        except PyJWTError:
            return None
