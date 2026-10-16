"""Captura remota de evidencias documentales.

El asesor crea una sesión desde el paso 3 del wizard; el cliente recibe
un link con token (QR en pantalla o WhatsApp) y sube desde su celular,
sin autenticarse: el token es la autorización y caduca rápido.

Storage: disco local (`evidencias_dir`) para el MVP — la interfaz
queda detrás de este servicio para migrar a S3/URLs prefirmadas en
producción sin tocar rutas ni frontend.
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from backend.config import get_settings
from backend.db_models.evidencia_models import DocumentoEvidencia, SesionCaptura
from backend.repositories.evidencia_repository import EvidenciaRepository
from backend.services.motor_exceptions import SolicitudNoEncontradaError, ValidacionError
from backend.services.ocr_service import procesar_foto_cedula

# Tipos de evidencia aceptados y MIME permitidos por cada uno.
# Imágenes: jpeg/png/webp + los formatos que generan los celulares
# (heic/heif en iPhone, avif en Android reciente, jpg genérico).
# Videos: lo que produce MediaRecorder (webm/mp4) y capturas nativas
# de celular (quicktime en iOS, 3gpp en Android antiguo).
_MIMES_IMAGEN = frozenset({
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
    "image/avif",
})
_MIMES_VIDEO = frozenset({
    "video/webm",
    "video/mp4",
    "video/quicktime",
    "video/3gpp",
    "video/3gpp2",
    "video/x-m4v",
})

TIPOS_EVIDENCIA: dict[str, frozenset[str]] = {
    "cedula_frontal": _MIMES_IMAGEN,
    "cedula_reverso": _MIMES_IMAGEN,
    "video_prueba_vida": _MIMES_VIDEO,
}

TIPOS_CEDULA = ("cedula_frontal", "cedula_reverso")

_EXTENSIONES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heif",
    "image/avif": ".avif",
    "video/webm": ".webm",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/3gpp": ".3gp",
    "video/3gpp2": ".3g2",
    "video/x-m4v": ".m4v",
}


class EvidenciaService:
    def __init__(self, db: Session) -> None:
        self.repo = EvidenciaRepository(db)
        self.settings = get_settings()

    # ------------------------------------------------------------------
    # Sesiones (lado del asesor)
    # ------------------------------------------------------------------
    def crear_sesion(self, datos_esperados: dict | None = None) -> SesionCaptura:
        sesion = SesionCaptura(
            token=secrets.token_urlsafe(32),
            expira_en=datetime.now(timezone.utc)
            + timedelta(minutes=self.settings.captura_ttl_minutos),
            datos_esperados=datos_esperados or None,
        )
        return self.repo.crear_sesion(sesion)

    def estado_sesion(self, sesion_id: uuid.UUID) -> SesionCaptura:
        sesion = self.repo.db.get(SesionCaptura, sesion_id)
        if sesion is None:
            raise SolicitudNoEncontradaError("Sesión de captura no encontrada")
        self._refrescar_expiracion(sesion)
        return sesion

    def enlazar_solicitud(self, token: str, id_solicitud: uuid.UUID) -> None:
        """Liga la sesión (y sus evidencias) a la solicitud recién creada.

        Tolera sesiones expiradas: las evidencias ya subidas siguen siendo
        válidas; la expiración solo bloquea subidas nuevas.
        """
        sesion = self.repo.obtener_sesion_por_token(token)
        if sesion is None:
            raise ValidacionError("Token de sesión de captura inválido")
        sesion.id_solicitud = id_solicitud
        for evidencia in self.repo.listar_evidencias(sesion.id_sesion):
            evidencia.id_solicitud = id_solicitud
        self.repo.db.flush()

    # ------------------------------------------------------------------
    # Captura (lado del cliente, con token)
    # ------------------------------------------------------------------
    def sesion_por_token(self, token: str) -> SesionCaptura:
        return self._sesion_vigente(token)

    def registrar_evidencia(
        self, token: str, tipo: str, archivo: UploadFile
    ) -> DocumentoEvidencia:
        sesion = self._sesion_vigente(token)
        if tipo not in TIPOS_EVIDENCIA:
            raise ValidacionError(f"Tipo de evidencia inválido: {tipo}")
        # El Content-Type puede traer parámetros (video/webm;codecs=vp9);
        # validar solo el tipo base.
        mime = (archivo.content_type or "application/octet-stream").split(";")[0].strip().lower()
        if mime not in TIPOS_EVIDENCIA[tipo]:
            raise ValidacionError(
                f"Tipo de archivo no permitido para {tipo}: {mime}"
            )

        contenido = archivo.file.read()
        max_bytes = self.settings.evidencia_max_mb * 1024 * 1024
        if len(contenido) > max_bytes:
            raise ValidacionError(
                f"El archivo supera el máximo de {self.settings.evidencia_max_mb} MB"
            )
        if not contenido:
            raise ValidacionError("El archivo está vacío")

        nombre = f"{tipo}_{uuid.uuid4().hex}{_EXTENSIONES[mime]}"
        ruta_relativa = str(Path(str(sesion.id_sesion)) / nombre)
        destino = Path(self.settings.evidencias_dir) / ruta_relativa
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(contenido)

        evidencia = DocumentoEvidencia(
            id_sesion=sesion.id_sesion,
            id_solicitud=sesion.id_solicitud,
            tipo=tipo,
            ruta=ruta_relativa,
            nombre_original=archivo.filename,
            mime=mime,
            tamano_bytes=len(contenido),
            hash_sha256=hashlib.sha256(contenido).hexdigest(),
        )
        ruta_previa = self.repo.reemplazar_evidencia(sesion.id_sesion, tipo, evidencia)
        if ruta_previa:
            (Path(self.settings.evidencias_dir) / ruta_previa).unlink(missing_ok=True)

        subidos = {e.tipo for e in self.repo.listar_evidencias(sesion.id_sesion)}
        if subidos >= set(TIPOS_EVIDENCIA):
            sesion.estado = "completada"
        # OCR de cada cara de la cédula. El resultado de anverso y reverso se
        # fusiona en la sesión (sin importar el orden de subida) y se compara
        # contra lo digitado en el paso 1 para advertir al asesor.
        if tipo in TIPOS_CEDULA:
            self._procesar_ocr(sesion, destino, tipo)
        self.repo.db.flush()
        return evidencia

    def _procesar_ocr(self, sesion: SesionCaptura, ruta: Path, tipo: str) -> None:
        """Lee la foto, la fusiona con la otra cara y guarda el resultado.

        Se asigna un dict nuevo: SQLAlchemy no detecta mutaciones internas de
        una columna JSON.
        """
        sesion.resultado_ocr = procesar_foto_cedula(
            sesion.resultado_ocr, tipo, ruta, sesion.datos_esperados or {}
        )

    def evidencias_de_sesion(self, sesion_id: uuid.UUID) -> list[DocumentoEvidencia]:
        return self.repo.listar_evidencias(sesion_id)

    def evidencias_de_solicitud(self, id_solicitud: uuid.UUID) -> list[DocumentoEvidencia]:
        return self.repo.listar_por_solicitud(id_solicitud)

    def archivo_evidencia(self, id_evidencia: int) -> tuple[Path, str]:
        evidencia = self.repo.obtener_evidencia(id_evidencia)
        if evidencia is None:
            raise SolicitudNoEncontradaError("Evidencia no encontrada")
        return Path(self.settings.evidencias_dir) / evidencia.ruta, evidencia.mime

    # ------------------------------------------------------------------
    def _sesion_vigente(self, token: str) -> SesionCaptura:
        sesion = self.repo.obtener_sesion_por_token(token)
        if sesion is None:
            raise SolicitudNoEncontradaError("Enlace de captura inválido")
        self._refrescar_expiracion(sesion)
        if sesion.estado == "expirada":
            raise ValidacionError("El enlace de captura expiró; pide uno nuevo al asesor")
        return sesion

    def _refrescar_expiracion(self, sesion: SesionCaptura) -> None:
        # SQLite devuelve datetimes naive; Postgres devuelve aware.
        expira = sesion.expira_en
        if expira.tzinfo is None:
            expira = expira.replace(tzinfo=timezone.utc)
        if sesion.estado != "expirada" and datetime.now(timezone.utc) > expira:
            sesion.estado = "expirada"
            self.repo.db.flush()
