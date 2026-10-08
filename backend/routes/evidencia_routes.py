"""Evidencias documentales: sesión de captura (asesor) y subida con token (cliente)."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db_models.session import get_db
from backend.services.evidencia_service import EvidenciaService, TIPOS_EVIDENCIA
from backend.services.motor_exceptions import SolicitudNoEncontradaError

router = APIRouter(tags=["evidencias"])


class SesionCapturaResponse(BaseModel):
    id_sesion: uuid.UUID
    token: str
    estado: str
    expira_en: str


def _sesion_response(s) -> SesionCapturaResponse:
    return SesionCapturaResponse(
        id_sesion=s.id_sesion,
        token=s.token,
        estado=s.estado,
        expira_en=s.expira_en.isoformat(),
    )


def _evidencia_dict(e) -> dict[str, Any]:
    return {
        "id_evidencia": e.id_evidencia,
        "tipo": e.tipo,
        "mime": e.mime,
        "tamano_bytes": e.tamano_bytes,
        "hash_sha256": e.hash_sha256,
        "creado_en": e.creado_en.isoformat(),
    }


# ---------------------------------------------------------------------------
# Lado del asesor (app autenticada)
# ---------------------------------------------------------------------------

@router.post("/sesiones-captura", response_model=SesionCapturaResponse, status_code=201)
def crear_sesion(db: Session = Depends(get_db)) -> SesionCapturaResponse:
    """Genera el link/QR de captura. La sesión nace sin solicitud: se enlaza
    cuando la solicitud se crea con `sesion_captura` en el payload."""
    return _sesion_response(EvidenciaService(db).crear_sesion())


@router.get("/sesiones-captura/{id_sesion}", response_model=dict)
def estado_sesion(id_sesion: uuid.UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Polling del asesor: estado de la sesión y evidencias recibidas."""
    servicio = EvidenciaService(db)
    sesion = servicio.estado_sesion(id_sesion)
    evidencias = servicio.evidencias_de_sesion(sesion.id_sesion)
    return {
        "id_sesion": str(sesion.id_sesion),
        "estado": sesion.estado,
        "expira_en": sesion.expira_en.isoformat(),
        "pendientes": sorted(set(TIPOS_EVIDENCIA) - {e.tipo for e in evidencias}),
        "evidencias": [_evidencia_dict(e) for e in evidencias],
    }


@router.get("/solicitudes/{id_solicitud}/evidencias", response_model=list[dict])
def evidencias_solicitud(id_solicitud: uuid.UUID, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [
        _evidencia_dict(e)
        for e in EvidenciaService(db).evidencias_de_solicitud(id_solicitud)
    ]


@router.get("/evidencias/{id_evidencia}/contenido")
def contenido_evidencia(id_evidencia: int, db: Session = Depends(get_db)) -> FileResponse:
    """Sirve el archivo de evidencia (lado del asesor; pendiente auth D101)."""
    ruta, mime = EvidenciaService(db).archivo_evidencia(id_evidencia)
    if not ruta.exists():
        raise SolicitudNoEncontradaError("Archivo de evidencia no encontrado")
    return FileResponse(ruta, media_type=mime)


# ---------------------------------------------------------------------------
# Lado del cliente (público, autoriza el token del link)
# ---------------------------------------------------------------------------

@router.get("/captura/{token}", response_model=dict)
def estado_captura(token: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Estado para la página móvil: qué evidencias faltan por subir."""
    servicio = EvidenciaService(db)
    sesion = servicio.sesion_por_token(token)
    evidencias = servicio.evidencias_de_sesion(sesion.id_sesion)
    return {
        "estado": sesion.estado,
        "pendientes": sorted(set(TIPOS_EVIDENCIA) - {e.tipo for e in evidencias}),
        "evidencias": [_evidencia_dict(e) for e in evidencias],
    }


@router.post("/captura/{token}/evidencias", response_model=dict, status_code=201)
def subir_evidencia(
    token: str,
    tipo: str = Form(...),
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    evidencia = EvidenciaService(db).registrar_evidencia(token, tipo, archivo)
    return _evidencia_dict(evidencia)
