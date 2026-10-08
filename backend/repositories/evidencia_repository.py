import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db_models.evidencia_models import DocumentoEvidencia, SesionCaptura


class EvidenciaRepository:
    """Persistencia de sesiones de captura y evidencias documentales."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def crear_sesion(self, sesion: SesionCaptura) -> SesionCaptura:
        self.db.add(sesion)
        self.db.flush()
        return sesion

    def obtener_sesion_por_token(self, token: str) -> SesionCaptura | None:
        return self.db.execute(
            select(SesionCaptura).where(SesionCaptura.token == token)
        ).scalar_one_or_none()

    def guardar_evidencia(self, evidencia: DocumentoEvidencia) -> DocumentoEvidencia:
        self.db.add(evidencia)
        self.db.flush()
        return evidencia

    def reemplazar_evidencia(self, sesion_id: uuid.UUID, tipo: str, nueva: DocumentoEvidencia) -> str | None:
        """Borra la evidencia previa del mismo tipo y retorna su ruta en disco para limpiar el archivo."""
        previa = self.db.execute(
            select(DocumentoEvidencia).where(
                DocumentoEvidencia.id_sesion == sesion_id,
                DocumentoEvidencia.tipo == tipo,
            )
        ).scalar_one_or_none()
        ruta_previa = previa.ruta if previa else None
        if previa:
            self.db.delete(previa)
        self.db.add(nueva)
        self.db.flush()
        return ruta_previa

    def listar_evidencias(self, sesion_id: uuid.UUID) -> list[DocumentoEvidencia]:
        return list(
            self.db.execute(
                select(DocumentoEvidencia)
                .where(DocumentoEvidencia.id_sesion == sesion_id)
                .order_by(DocumentoEvidencia.id_evidencia)
            ).scalars().all()
        )

    def listar_por_solicitud(self, id_solicitud: uuid.UUID) -> list[DocumentoEvidencia]:
        return list(
            self.db.execute(
                select(DocumentoEvidencia)
                .where(DocumentoEvidencia.id_solicitud == id_solicitud)
                .order_by(DocumentoEvidencia.id_evidencia)
            ).scalars().all()
        )

    def obtener_evidencia(self, id_evidencia: int) -> DocumentoEvidencia | None:
        return self.db.get(DocumentoEvidencia, id_evidencia)
