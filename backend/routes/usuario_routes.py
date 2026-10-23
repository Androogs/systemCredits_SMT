"""Administración de usuarios de la plataforma.

El admin gestiona todo; el concesionario solo los asesores de su sede
(el servicio aplica el alcance — la puerta solo exige el rol).
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.auth.dependencies import UsuarioActual, requiere_roles
from backend.db_models.session import get_db
from backend.models.auth_models import (
    ActualizarUsuarioRequest,
    AsesorHistorialResponse,
    CrearUsuarioRequest,
    OpcionesUsuarioResponse,
    RestablecerClaveRequest,
    UsuarioGestionResponse,
)
from backend.services.usuario_service import UsuarioService

router = APIRouter(
    prefix="/usuarios",
    tags=["usuarios"],
)


@router.get("", response_model=list[UsuarioGestionResponse])
def listar(
    usuario: UsuarioActual = Depends(requiere_roles("admin", "concesionario")),
    db: Session = Depends(get_db),
) -> list[UsuarioGestionResponse]:
    return UsuarioService(db).listar(usuario)


@router.get("/opciones", response_model=OpcionesUsuarioResponse)
def opciones(
    usuario: UsuarioActual = Depends(requiere_roles("admin", "concesionario")),
    db: Session = Depends(get_db),
) -> OpcionesUsuarioResponse:
    """Catálogos de los selects del formulario: roles, sedes y aliados.
    Para el concesionario vienen ya acotados a su sede."""
    return UsuarioService(db).opciones(usuario)


@router.post(
    "",
    response_model=UsuarioGestionResponse,
    status_code=status.HTTP_201_CREATED,
)
def crear(
    payload: CrearUsuarioRequest,
    usuario: UsuarioActual = Depends(requiere_roles("admin", "concesionario")),
    db: Session = Depends(get_db),
) -> UsuarioGestionResponse:
    """Alta con clave temporal: `requiere_cambio_password` queda en true
    para que el usuario la cambie en su primer ingreso. El
    concesionario solo puede crear asesores de su sede."""
    return UsuarioService(db).crear(payload, usuario)


@router.put("/{id_usuario}", response_model=UsuarioGestionResponse)
def actualizar(
    id_usuario: uuid.UUID,
    payload: ActualizarUsuarioRequest,
    usuario: UsuarioActual = Depends(requiere_roles("admin", "concesionario")),
    db: Session = Depends(get_db),
) -> UsuarioGestionResponse:
    """Edita nombre, estado, roles y vínculos (asesor→sede,
    usuario→aliado, usuario→sede). Los campos ausentes del payload no
    se tocan. Para el concesionario, el usuario objetivo debe ser un
    asesor de su sede."""
    return UsuarioService(db).actualizar(id_usuario, payload, usuario)


@router.post("/{id_usuario}/restablecer-clave", status_code=status.HTTP_204_NO_CONTENT)
def restablecer_clave(
    id_usuario: uuid.UUID,
    payload: RestablecerClaveRequest,
    usuario: UsuarioActual = Depends(requiere_roles("admin", "concesionario")),
    db: Session = Depends(get_db),
) -> None:
    """Fija una nueva clave temporal: desbloquea la cuenta y exige
    cambio en el próximo ingreso."""
    UsuarioService(db).restablecer_clave(
        id_usuario, payload.contrasena, usuario
    )


@router.get(
    "/{id_usuario}/historial",
    response_model=list[AsesorHistorialResponse],
)
def historial(
    id_usuario: uuid.UUID,
    usuario: UsuarioActual = Depends(requiere_roles("admin", "concesionario")),
    db: Session = Depends(get_db),
) -> list[AsesorHistorialResponse]:
    """Historial de cambios de la ficha del asesor (la persona detrás
    del correo puede cambiar — aquí queda quién cambió qué y cuándo).
    El concesionario solo puede consultar asesores de su sede."""
    return UsuarioService(db).historial(id_usuario, usuario)
