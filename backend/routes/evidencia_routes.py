"""Evidencias documentales: sesión de captura (asesor) y subida con token (cliente)."""

import io
import uuid
import zipfile
from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db_models.evidencia_models import DocumentoEvidencia
from backend.db_models.models import SolicitudCredito
from backend.db_models.session import get_db
from backend.services.documento_service import _TIPO_ID
from backend.services.evidencia_service import TIPOS_CEDULA, EvidenciaService, TIPOS_EVIDENCIA
from backend.services.motor_exceptions import SolicitudNoEncontradaError

router = APIRouter(tags=["evidencias"])


class SesionCapturaResponse(BaseModel):
    id_sesion: uuid.UUID
    token: str
    estado: str
    expira_en: str


class DatosEsperadosPayload(BaseModel):
    """Datos del paso 1 contra los que se compara el OCR de la cédula."""

    nombres: str | None = None
    apellidos: str | None = None
    numero_documento: str | None = None
    fecha_nacimiento: str | None = None


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
        "nombre_original": e.nombre_original,
        "mime": e.mime,
        "tamano_bytes": e.tamano_bytes,
        "hash_sha256": e.hash_sha256,
        "creado_en": e.creado_en.isoformat(),
    }


# ---------------------------------------------------------------------------
# Lado del asesor (app autenticada)
# ---------------------------------------------------------------------------

@router.post("/sesiones-captura", response_model=SesionCapturaResponse, status_code=201)
def crear_sesion(
    payload: DatosEsperadosPayload | None = None,
    db: Session = Depends(get_db),
) -> SesionCapturaResponse:
    """Genera el link/QR de captura. La sesión nace sin solicitud: se enlaza
    cuando la solicitud se crea con `sesion_captura` en el payload.

    Los `datos_esperados` (paso 1) se guardan para comparar contra el OCR de
    la cédula y advertir sobre no coincidencias.
    """
    esperados = payload.model_dump(exclude_none=True) if payload else None
    return _sesion_response(EvidenciaService(db).crear_sesion(esperados))


@router.get("/sesiones-captura/{id_sesion}", response_model=dict)
def estado_sesion(id_sesion: uuid.UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Polling del asesor: estado de la sesión, evidencias recibidas y OCR
    fusionado de anverso + reverso."""
    servicio = EvidenciaService(db)
    sesion = servicio.estado_sesion(id_sesion)
    evidencias = servicio.evidencias_de_sesion(sesion.id_sesion)
    return {
        "id_sesion": str(sesion.id_sesion),
        "estado": sesion.estado,
        "expira_en": sesion.expira_en.isoformat(),
        "pendientes": sorted(set(TIPOS_EVIDENCIA) - {e.tipo for e in evidencias}),
        "evidencias": [_evidencia_dict(e) for e in evidencias],
        "ocr": sesion.resultado_ocr,
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


@router.get("/solicitudes/{id_solicitud}/legalizacion.zip")
def paquete_legalizacion(
    id_solicitud: uuid.UUID, db: Session = Depends(get_db)
) -> Response:
    """Todos los documentos del paquete de legalización (doc_*) en un .zip."""
    servicio = EvidenciaService(db)
    documentos = [
        e
        for e in servicio.evidencias_de_solicitud(id_solicitud)
        if e.tipo.startswith("doc_")
    ]
    if not documentos:
        raise SolicitudNoEncontradaError(
            "La solicitud no tiene documentos de legalización"
        )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as paquete:
        for doc in documentos:
            ruta, _ = servicio.archivo_evidencia(doc.id_evidencia)
            if ruta.exists():
                paquete.write(ruta, doc.nombre_original or f"{doc.tipo}.docx")
    solicitud = db.get(SolicitudCredito, id_solicitud)
    numero = solicitud.num_solicitud if solicitud else str(id_solicitud)[:8]
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="legalizacion-{numero}.zip"'
        },
    )


# ---------------------------------------------------------------------------
# Lado del cliente (público, autoriza el token del link)
# ---------------------------------------------------------------------------

@router.get("/captura/{token}", response_model=dict)
def estado_captura(token: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Estado para la página móvil: qué evidencias faltan por subir.

    No expone el resultado del OCR: es un endpoint público (solo token) y el
    resultado incluye datos personales y lo que digitó el asesor. El celular
    solo necesita saber si la cédula se pudo leer para pedir repetir la foto.
    """
    servicio = EvidenciaService(db)
    sesion = servicio.sesion_por_token(token)
    evidencias = servicio.evidencias_de_sesion(sesion.id_sesion)
    ocr = sesion.resultado_ocr or {}
    lecturas = ocr.get("lecturas") or {}
    return {
        "estado": sesion.estado,
        "pendientes": sorted(set(TIPOS_EVIDENCIA) - {e.tipo for e in evidencias}),
        "evidencias": [_evidencia_dict(e) for e in evidencias],
        # Por cara: True si se reconoció la cédula en la foto (sugerir repetirla si False).
        "cedula_legible": {
            tipo: bool((lecturas.get(tipo) or {}).get("tipo_cedula"))
            for tipo in TIPOS_CEDULA
            if tipo in lecturas
        },
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


@router.get("/firmas/{uuid_firma}", response_model=dict)
def verificar_firma(
    uuid_firma: uuid.UUID, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Verificación pública de la firma electrónica (OTP): es el destino
    del QR estampado en los documentos de legalización. Solo devuelve lo
    impreso en el propio documento — permite a un tercero contrastar que
    la firma existe y a quién pertenece."""
    solicitud = (
        db.query(SolicitudCredito)
        .filter(SolicitudCredito.uuid_firma == uuid_firma)
        .first()
    )
    if solicitud is None or solicitud.fecha_hora_firma is None:
        raise SolicitudNoEncontradaError("Firma no encontrada")
    cliente = solicitud.cliente
    documentos = (
        db.query(DocumentoEvidencia)
        .filter(
            DocumentoEvidencia.id_solicitud == solicitud.id_solicitud,
            DocumentoEvidencia.tipo.like("doc_%"),
        )
        .count()
    )
    return {
        "uuid_firma": str(solicitud.uuid_firma),
        "num_solicitud": solicitud.num_solicitud,
        "firmante": cliente.nombre_completo if cliente else "",
        "documento_identidad": (
            f"{_TIPO_ID.get(str(cliente.tipo_documento), str(cliente.tipo_documento))}"
            f" {cliente.num_cedula}"
            if cliente
            else ""
        ),
        "fecha_hora_firma": solicitud.fecha_hora_firma.isoformat(),
        "autenticacion": solicitud.autenticacion,
        "documentos": documentos,
    }
