"""Factura del vehículo: carga, verificación y datos de la prenda.

La factura la emite el concesionario tras la firma del pagaré y la sube
el asesor: no es solo guardar un archivo — el PDF se lee, se verifica
contra la solicitud (¿es la factura de ESTE cliente?) y alimenta la
prenda (motor/chasis/VIN no se capturan en originación). Su carga mueve
el ciclo comercial aprobada → facturada → desembolsada.

Storage: disco local (`evidencias_dir`), igual que evidencias y el
paquete de legalización.
"""

import hashlib
import logging
import re
import shutil
import subprocess
import unicodedata
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from backend.config import get_settings
from backend.db_models.models import ProductoVehiculo, SolicitudCredito
from backend.integrations.factura.factura_parser import (
    DatosFactura,
    extraer_y_parsear,
    nombres_coinciden,
    solo_digitos,
)
from backend.models.solicitud_models import PrendaVehiculoRequest
from backend.repositories.solicitud_repository import SolicitudRepository
from backend.services.documento_service import DocumentoService
from backend.services.motor_exceptions import (
    ConflictoEstadoError,
    SolicitudNoEncontradaError,
    ValidacionError,
)

logger = logging.getLogger(__name__)

_MIMES_FACTURA = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _norm(valor: str | None) -> str:
    base = unicodedata.normalize("NFKD", valor or "")
    sin_tildes = "".join(c for c in base if not unicodedata.combining(c))
    return re.sub(r"[^A-Z0-9]+", " ", sin_tildes.upper()).strip()


def _tokens(valor: str | None) -> set[str]:
    return {t for t in _norm(valor).split(" ") if t}


def _vehiculo_de(db: Session, id_solicitud: uuid.UUID) -> ProductoVehiculo | None:
    return (
        db.query(ProductoVehiculo)
        .filter(ProductoVehiculo.id_solicitud == id_solicitud)
        .order_by(ProductoVehiculo.id_vehiculo.desc())
        .first()
    )


class FacturaService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = SolicitudRepository(db)
        self.settings = get_settings()

    # ------------------------------------------------------------------
    # Carga
    # ------------------------------------------------------------------
    def registrar_factura(
        self,
        id_solicitud: uuid.UUID,
        archivo: UploadFile,
        cargada_por: str,
    ) -> dict:
        """Guarda la factura, la verifica contra la solicitud y mueve el
        estado a 'facturada'. Devuelve el payload de FacturaResponse.

        El NIT del comprador distinto al de la solicitud bloquea la
        carga (422) ANTES de escribir el archivo: facturar con la
        factura de otro es el único error que no se admite ni con
        advertencia. Todo lo demás queda persistido como advertencia.
        """
        solicitud = self.repo.obtener_detalle(id_solicitud)
        if solicitud is None:
            raise SolicitudNoEncontradaError(f"No existe la solicitud {id_solicitud}")
        # Una venta de contado no pasa por evaluación ni pagaré: la
        # factura se carga apenas radicada (estado 'creada').
        es_contado = (solicitud.linea_credito or "").strip().casefold() == "contado"
        if es_contado:
            if solicitud.estado not in ("creada", "facturada"):
                raise ConflictoEstadoError(
                    f"La solicitud está '{solicitud.estado}'; la factura de "
                    "una venta de contado se carga recién radicada (o ya "
                    "facturada, para re-subirla)."
                )
        else:
            # El pagaré firmado es la precondición: sin OTP no hay crédito
            # formalizado que facturar.
            if solicitud.decision != "aprobado" or solicitud.fecha_hora_firma is None:
                raise ConflictoEstadoError(
                    "La factura se carga una vez el pagaré está firmado por OTP."
                )
            if solicitud.estado not in ("aprobada", "facturada"):
                raise ConflictoEstadoError(
                    f"La solicitud está '{solicitud.estado}'; la factura solo se "
                    "carga estando aprobada (o ya facturada, para re-subirla)."
                )

        mime = (archivo.content_type or "application/octet-stream").split(";")[0].strip().lower()
        if mime not in _MIMES_FACTURA:
            raise ValidacionError(
                "Tipo de archivo no permitido para la factura: "
                f"{mime or 'desconocido'} (admite PDF e imágenes)."
            )
        contenido = archivo.file.read()
        max_bytes = self.settings.evidencia_max_mb * 1024 * 1024
        if not contenido:
            raise ValidacionError("El archivo está vacío")
        if len(contenido) > max_bytes:
            raise ValidacionError(
                f"El archivo supera el máximo de {self.settings.evidencia_max_mb} MB"
            )

        datos = extraer_y_parsear(contenido, mime)
        verificacion = self._verificar_factura(solicitud, datos)

        # Persistencia: un solo archivo vigente por solicitud; si la
        # extensión cambia se borra el anterior (no quedan dos).
        extension = _MIMES_FACTURA[mime]
        ruta_relativa = f"facturas/{id_solicitud}/factura{extension}"
        destino = Path(self.settings.evidencias_dir) / ruta_relativa
        destino.parent.mkdir(parents=True, exist_ok=True)
        ruta_previa = solicitud.factura_ruta
        destino.write_bytes(contenido)
        if ruta_previa and ruta_previa != ruta_relativa:
            (Path(self.settings.evidencias_dir) / ruta_previa).unlink(missing_ok=True)

        solicitud.factura_ruta = ruta_relativa
        solicitud.factura_nombre = archivo.filename
        solicitud.factura_mime = mime
        solicitud.factura_hash = hashlib.sha256(contenido).hexdigest()
        solicitud.factura_cargada_en = datetime.now(UTC)
        solicitud.factura_cargada_por = cargada_por
        solicitud.factura_verificacion = verificacion
        if datos is not None:
            self._aplicar_datos_factura(solicitud, datos)
        self._regenerar_prenda(solicitud)
        if solicitud.estado == "aprobada" or (
            es_contado and solicitud.estado == "creada"
        ):
            solicitud.estado = "facturada"
            solicitud.descripcion_estado = (
                "Factura registrada; venta de contado cerrada."
                if es_contado
                else "Factura del vehículo registrada; pendiente desembolso."
            )
        self.db.flush()
        return self.factura_response(solicitud)

    # ------------------------------------------------------------------
    # Verificación
    # ------------------------------------------------------------------
    def _verificar_factura(
        self, solicitud: SolicitudCredito, datos: DatosFactura | None
    ) -> dict:
        """Contrasta lo extraído con la solicitud. Devuelve el dict que
        se persiste en factura_verificacion (parseada, nit_coincide,
        advertencias, datos)."""
        advertencias: list[str] = []
        if datos is None:
            return {
                "parseada": False,
                "nit_coincide": None,
                "advertencias": [
                    "No se pudo leer el texto de la factura; verifique "
                    "manualmente que corresponda al cliente."
                ],
                "datos": None,
            }

        cliente = solicitud.cliente
        nit_factura = solo_digitos(datos.nit_comprador)
        # En la venta de contado la factura puede expedirse a un tercero
        # ('facturar a'): si está registrado, la verificación es contra
        # él y no contra el cliente.
        nit_esperado = solo_digitos(solicitud.facturar_a_documento) or solo_digitos(
            cliente.num_cedula if cliente else None
        )
        nombre_esperado = solicitud.facturar_a_nombre or (
            cliente.nombre_completo if cliente else None
        )
        if nit_factura:
            if nit_factura != nit_esperado:
                # Bloqueante: la factura es de otra persona.
                raise ValidacionError(
                    f"La factura {datos.numero_factura or ''} corresponde a otro "
                    f"comprador (documento {nit_factura}); la solicitud es de "
                    f"{nit_esperado or 'otro titular'}."
                )
            nit_coincide = True
        else:
            nit_coincide = None
            advertencias.append(
                "La factura no muestra el documento del comprador; verifique "
                "que corresponda al cliente."
            )

        if nombres_coinciden(datos.nombre_comprador, nombre_esperado) is False:
            advertencias.append(
                f"Comprador: la factura indica '{datos.nombre_comprador}' y la "
                f"solicitud registró '{nombre_esperado}'."
            )

        vehiculo = _vehiculo_de(self.db, solicitud.id_solicitud)
        if vehiculo is not None:
            if datos.marca and vehiculo.marca and _norm(datos.marca) != _norm(vehiculo.marca):
                advertencias.append(
                    f"Marca: la factura indica '{datos.marca}' y la oferta "
                    f"registró '{vehiculo.marca}'."
                )
            tf, tv = _tokens(datos.referencia or datos.linea), _tokens(vehiculo.referencia)
            if tf and tv and not (tf <= tv or tv <= tf):
                advertencias.append(
                    f"Referencia: la factura indica '{datos.referencia or datos.linea}' "
                    f"y la oferta registró '{vehiculo.referencia}'."
                )
            if datos.anio and vehiculo.modelo and str(datos.anio) != str(vehiculo.modelo):
                advertencias.append(
                    f"Modelo (año): la factura indica '{datos.anio}' y la "
                    f"oferta registró '{vehiculo.modelo}'."
                )
            if datos.color and vehiculo.color and _norm(datos.color) != _norm(vehiculo.color):
                advertencias.append(
                    f"Color: la factura indica '{datos.color}', que queda como "
                    f"definitivo (la oferta registró '{vehiculo.color}')."
                )
        return {
            "parseada": True,
            "nit_coincide": nit_coincide,
            "advertencias": advertencias,
            "datos": datos.como_dict(),
        }

    # ------------------------------------------------------------------
    # Aplicación a la prenda
    # ------------------------------------------------------------------
    def _aplicar_datos_factura(
        self, solicitud: SolicitudCredito, datos: DatosFactura
    ) -> None:
        """Pre-llena la prenda con lo que dice la factura: motor/chasis/
        VIN solo si están vacíos, marca/referencia/modelo igual; el
        color SIEMPRE manda (es el de la moto real)."""
        vehiculo = _vehiculo_de(self.db, solicitud.id_solicitud)
        if vehiculo is None:
            vehiculo = ProductoVehiculo(
                id_solicitud=solicitud.id_solicitud,
                producto_a_financiar=solicitud.destino_credito or "Motocicleta",
            )
            self.db.add(vehiculo)
        for campo, valor in (
            ("numero_motor", datos.numero_motor),
            ("numero_chasis", datos.numero_chasis or datos.vin),
            ("vin", datos.vin or datos.numero_chasis),
            ("marca", datos.marca),
            ("referencia", datos.referencia or datos.linea),
            ("modelo", datos.anio),
        ):
            if valor and not getattr(vehiculo, campo):
                setattr(vehiculo, campo, valor)
        if datos.color:
            vehiculo.color = datos.color

    # ------------------------------------------------------------------
    # Regeneración del paquete legal (prenda con motor/chasis)
    # ------------------------------------------------------------------
    def _regenerar_prenda(self, solicitud: SolicitudCredito) -> None:
        """La prenda firmada quedó sin motor/chasis (llegan con la
        factura): se regenera el paquete legal completo. SAVEPOINT +
        best-effort: un fallo no revierte la carga de la factura."""
        if solicitud.fecha_hora_firma is None:
            return
        try:
            with self.db.begin_nested():
                DocumentoService(self.db).generar_paquete(solicitud.id_solicitud)
        except Exception:  # noqa: BLE001
            logger.exception(
                "No se pudo regenerar el paquete legal de la solicitud %s",
                solicitud.id_solicitud,
            )

    # ------------------------------------------------------------------
    # Corrección manual de la prenda (PATCH /vehiculo)
    # ------------------------------------------------------------------
    def actualizar_prenda(
        self, id_solicitud: uuid.UUID, payload: PrendaVehiculoRequest
    ) -> dict:
        """El asesor confirma/corrige la identificación de la moto
        prendada; solo estando 'facturada' (la factura es el insumo)."""
        solicitud = self.repo.obtener_detalle(id_solicitud)
        if solicitud is None:
            raise SolicitudNoEncontradaError(f"No existe la solicitud {id_solicitud}")
        if solicitud.estado != "facturada":
            raise ConflictoEstadoError(
                "Los datos de la prenda solo se confirman con la solicitud "
                f"facturada (estado actual: {solicitud.estado})."
            )
        vehiculo = _vehiculo_de(self.db, id_solicitud)
        if vehiculo is None:
            vehiculo = ProductoVehiculo(
                id_solicitud=id_solicitud,
                producto_a_financiar=solicitud.destino_credito or "Motocicleta",
            )
            self.db.add(vehiculo)
        for campo in (
            "marca", "referencia", "modelo", "color",
            "numero_motor", "numero_chasis", "vin",
        ):
            valor = getattr(payload, campo, None)
            if valor is not None:
                setattr(vehiculo, campo, valor.strip() or None)
        self._regenerar_prenda(solicitud)
        self.db.flush()
        return {
            "marca": vehiculo.marca,
            "referencia": vehiculo.referencia,
            "modelo": vehiculo.modelo,
            "color": vehiculo.color,
            "numero_motor": vehiculo.numero_motor,
            "numero_chasis": vehiculo.numero_chasis,
            "vin": vehiculo.vin,
            "valor_moto_iva": vehiculo.valor_moto_iva,
        }

    # ------------------------------------------------------------------
    # Lectura / exposición
    # ------------------------------------------------------------------
    def factura_archivo(self, id_solicitud: uuid.UUID) -> tuple[Path, str, str]:
        """(ruta, mime, nombre) de la factura vigente; 404 sin factura."""
        solicitud = self.db.get(SolicitudCredito, id_solicitud)
        if solicitud is None or not solicitud.factura_ruta:
            raise SolicitudNoEncontradaError(
                "La solicitud no tiene factura registrada"
            )
        ruta = Path(self.settings.evidencias_dir) / solicitud.factura_ruta
        if not ruta.exists():
            raise SolicitudNoEncontradaError(
                "El archivo de la factura no está en disco"
            )
        return ruta, solicitud.factura_mime or "application/octet-stream", (
            solicitud.factura_nombre or "factura.pdf"
        )

    def factura_response(self, solicitud: SolicitudCredito) -> dict:
        """El detalle re-renderiza desde los metadatos persistidos, sin
        releer el PDF."""
        if not solicitud.factura_ruta:
            return None
        verificacion = solicitud.factura_verificacion or None
        if verificacion and isinstance(verificacion.get("datos"), dict):
            total = verificacion["datos"].get("total")
            if isinstance(total, Decimal):
                verificacion["datos"]["total"] = str(total)
        return {
            "nombre": solicitud.factura_nombre,
            "mime": solicitud.factura_mime,
            "hash_sha256": solicitud.factura_hash,
            "cargada_en": (
                solicitud.factura_cargada_en.isoformat()
                if solicitud.factura_cargada_en else None
            ),
            "cargada_por": solicitud.factura_cargada_por,
            "verificacion": verificacion,
        }

    # ------------------------------------------------------------------
    # Envío del paquete definitivo (factura registrada = moto prendada)
    # ------------------------------------------------------------------
    def enviar_documentos_finales(self, id_solicitud: uuid.UUID) -> dict:
        """Con la factura la moto ya quedó prendada: es el momento de
        enviar al cliente el paquete definitivo (NO al firmar el OTP —
        la prenda iría sin motor/chasis).

        Regenera el paquete dentro de SAVEPOINT (la factura está en
        flush, sin commit — un rollback la perdería), convierte cada
        DOCX a PDF junto a los originales (subcarpeta pdf/) y notifica.
        Best-effort: la factura ya quedó; el resultado viaja en la
        respuesta para que operaciones vea el fallo y reenvíe recargando.
        """
        from backend.services.notificacion_service import NotificacionService

        entrega = {"paquete_generado": False, "pdfs_adjuntos": 0, "correo_estado": None}
        solicitud = self.repo.obtener_detalle(id_solicitud)
        if solicitud is None:
            return entrega
        try:
            with self.db.begin_nested():
                docs = DocumentoService(self.db).generar_paquete(id_solicitud)
        except Exception:  # noqa: BLE001
            logger.exception(
                "No se pudo regenerar el paquete legal de %s", id_solicitud
            )
            docs = []
        entrega["paquete_generado"] = bool(docs)

        adjuntos = self._convertir_paquete_a_pdf(docs, id_solicitud)
        entrega["pdfs_adjuntos"] = len(adjuntos)

        try:
            if adjuntos:
                envio = NotificacionService().notificar(
                    "legalizacion", solicitud, adjuntos=adjuntos
                )
            elif docs:
                # Paquete generado pero sin conversor (soffice ausente):
                # avisa igual; el fallo queda en log.
                envio = NotificacionService().notificar("legalizacion", solicitud)
            else:
                # Sin paquete (sin firma): solo avisa el registro.
                envio = NotificacionService().notificar("factura", solicitud)
            entrega["correo_estado"] = envio["estado"]
        except Exception:  # noqa: BLE001
            logger.exception(
                "Falló el correo de documentos finales de %s", id_solicitud
            )
            entrega["correo_estado"] = "error"
        return entrega

    def _convertir_paquete_a_pdf(
        self, docs, id_solicitud: uuid.UUID
    ) -> list[Path]:
        """Convierte cada DOCX del paquete a PDF en la subcarpeta pdf/,
        junto a los originales. Sin `soffice`/`libreoffice` en el PATH
        devuelve [] (el correo sale sin adjuntos y queda en log)."""
        if not docs:
            return []
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if soffice is None:
            logger.warning(
                "Sin conversor DOCX→PDF (soffice/libreoffice ausente); el "
                "correo de legalización de %s sale sin adjuntos",
                id_solicitud,
            )
            return []
        base = Path(self.settings.evidencias_dir)
        pdf_dir = base / "legalizacion" / str(id_solicitud) / "pdf"
        pdf_dir.mkdir(parents=True, exist_ok=True)
        rutas = [base / d.ruta for d in docs if (base / d.ruta).exists()]
        if not rutas:
            return []
        try:
            subprocess.run(
                [
                    soffice, "--headless", "--convert-to", "pdf",
                    "--outdir", str(pdf_dir),
                    *(str(r) for r in rutas),
                ],
                timeout=180,
                check=False,
                capture_output=True,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Falló la conversión DOCX→PDF de %s", id_solicitud)
            return []
        pdfs = [
            pdf_dir / f"{r.stem}.pdf" for r in rutas
            if (pdf_dir / f"{r.stem}.pdf").exists()
        ]
        return pdfs
