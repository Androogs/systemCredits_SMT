"""Dependencias FastAPI de autenticación y autorización.

`usuario_actual` exige un `Authorization: Bearer <jwt>` válido y un
usuario `activo` vigente en BD (el estado y los roles se re-lean por
request: revocar acceso surte efecto dentro del TTL del token).

`requiere_roles(*roles)` encadena sobre `usuario_actual` y responde 403
cuando ninguno de los roles del usuario coincide.

Endpoints públicos por diseño (sin estas dependencias): /health, /,
/auth/login, /captura/{token}, /firmas/{uuid}, /webhook/desembolso
(firma HMAC propia).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.config import Settings, get_settings
from backend.db_models.session import get_db
from backend.repositories.usuario_repository import UsuarioRepository
from backend.services.jwt_service import JwtService

_bearer = HTTPBearer(auto_error=False)

_CREDENCIALES_INVALIDAS = "Sesión inválida o expirada. Inicia sesión de nuevo."


@dataclass
class UsuarioActual:
    """Contexto del usuario autenticado para alcance y auditoría."""

    id_usuario: uuid.UUID
    correo: str
    nombre: str
    roles: list[str]
    id_asesor: int | None = None
    # Cédula de la persona detrás de la cuenta de asesor: el alcance de
    # radicaciones es por persona — si la cuenta cambia de dueño, las
    # solicitudes del anterior dejan de ser visibles para el nuevo.
    cedula_asesor: str | None = None
    # Corte temporal del titular actual: las solicitudes legadas sin
    # foto de cédula solo las ve quien estaba al crearlas.
    persona_desde_asesor: datetime | None = None
    id_concesionario: int | None = None
    id_aliados: tuple[int, ...] = field(default_factory=tuple)
    concesionarios_aliado: tuple[int, ...] = field(default_factory=tuple)

    def es_admin(self) -> bool:
        return "admin" in self.roles

    def es_concesionario(self) -> bool:
        return "concesionario" in self.roles

    def concesionario_ids(self) -> set[int] | None:
        """Concesionarios cuyas solicitudes puede ver.

        - admin → None (sin filtro, ve todo)
        - asesor → su sede (sin sede asignada → set vacío: no ve nada)
        - concesionario → su sede (vínculo `concesionario_usuario`)
        - aliado → los concesionarios vigentes de su aliado
        """
        if self.es_admin():
            return None
        if "asesor" in self.roles or self.es_concesionario():
            return (
                {self.id_concesionario}
                if self.id_concesionario is not None
                else set()
            )
        return set(self.concesionarios_aliado)

    def asesor_ids(self) -> set[int] | None:
        """Radicaciones propias alcanzables (eje "quién la creó").

        - asesor → solo las que radicó él; sin ficha de asesor → set
          vacío (fail-closed, no ve nada)
        - concesionario → None: ve todas las de su sede (administra,
          no radica a su nombre)
        - admin/aliado → None: su alcance va por el eje concesionario;
          el aliado ve todas las de sus sedes para el reporte de
          comisiones por radicador.
        """
        if self.es_admin() or self.es_concesionario():
            return None
        if "asesor" in self.roles:
            return (
                {self.id_asesor} if self.id_asesor is not None else set()
            )
        return None

    def aliado_ids(self) -> set[int]:
        return set(self.id_aliados)


def usuario_actual(
    credenciales: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer)
    ],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UsuarioActual:
    no_valido = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=_CREDENCIALES_INVALIDAS,
    )
    if credenciales is None or credenciales.scheme.lower() != "bearer":
        raise no_valido

    claims = JwtService(settings).decodificar(credenciales.credentials)
    if claims is None:
        raise no_valido
    try:
        id_usuario = uuid.UUID(str(claims.get("sub")))
    except (ValueError, AttributeError, TypeError):
        raise no_valido

    repo = UsuarioRepository(db)
    usuario = repo.por_id(id_usuario)
    if usuario is None or usuario.estado != "activo":
        raise no_valido

    asesor = repo.asesor_de(usuario.id_usuario)
    sede_administrada = repo.concesionario_de_concesionario(
        usuario.id_usuario
    )
    actual = UsuarioActual(
        id_usuario=usuario.id_usuario,
        correo=usuario.correo,
        nombre=usuario.nombre_completo or usuario.correo,
        roles=repo.roles_de(usuario.id_usuario),
        id_asesor=asesor.id_asesor if asesor else None,
        cedula_asesor=asesor.num_cedula if asesor else None,
        persona_desde_asesor=asesor.persona_desde if asesor else None,
        id_concesionario=(
            asesor.id_concesionario
            if asesor
            else (sede_administrada.id_concesionario if sede_administrada else None)
        ),
        id_aliados=tuple(repo.aliados_de(usuario.id_usuario)),
        concesionarios_aliado=tuple(
            repo.concesionarios_de_aliado(usuario.id_usuario)
        ),
    )

    # Los triggers de auditoría (auditoria_cambio, historial de estado)
    # leen app.user_id: Postgres-only, en SQLite no aplica.
    # SET LOCAL no acepta parámetros bindeados — set_config(..., true)
    # es el equivalente transaccional parametrizable.
    if db.bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": str(actual.id_usuario)},
        )
    return actual


def requiere_roles(*roles_requeridos: str):
    """Dependencia que exige al menos uno de los roles dados."""

    def _dependencia(
        usuario: Annotated[UsuarioActual, Depends(usuario_actual)],
    ) -> UsuarioActual:
        if not set(usuario.roles) & set(roles_requeridos):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para esta operación.",
            )
        return usuario

    return _dependencia
