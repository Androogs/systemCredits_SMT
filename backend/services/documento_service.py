"""Paquete de legalización: llena las plantillas DOCX (MERGEFIELDs)
con los datos capturados en el proceso y los registra como evidencias
de la solicitud.

Se dispara al verificar el OTP de firma (`firma_pagare`): el cliente
firma una sola vez y el paquete completo queda sellado con
`fecha_hora_firma` / `uuid_firma`.

Documentos generados:
1. Autorización consulta centrales (mailmerge)
2. Carta de aprobación (mailmerge)
3. Pagaré (mailmerge + “Consecutivo” = num_solicitud)
4. Carta de instrucciones (mailmerge + "No 001" = consecutivo)
5. Prenda sin tenencia (mailmerge)
6. Declaración de asegurabilidad (generada con python-docx; la
   plantilla fuente está en .doc binario que no admite merge)
7. Solicitud de crédito (plantilla con tokens {{CAMPO}} generada por
   scripts/generar_plantilla_solicitud.py desde el formato real)
8. Compromiso de pago y política de cartera (la fuente venía
   diligenciada con datos de muestra; se sustituyen por el titular)

Todos los documentos llevan estampado el uuid_firma de la firma
electrónica (OTP) como trazabilidad del acto de firma.
"""

import hashlib
import io
import secrets
import shutil
import uuid
import zipfile
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape as _xml_escape

import segno
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from mailmerge import MailMerge
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.db_models.evidencia_models import DocumentoEvidencia, SesionCaptura
from backend.db_models.models import (
    CreditoFinanciacion,
    OfertaCredito,
    ProductoVehiculo,
    SolicitudCredito,
)
from backend.repositories.evidencia_repository import EvidenciaRepository
from backend.repositories.solicitud_repository import SolicitudRepository
from backend.services.finanzas import cuota_anualidad
from backend.services.letras import numero_a_letras
from backend.services.motor_exceptions import SolicitudNoEncontradaError
from backend.services.seguro_service import cuota_seguro, seguro_vida_vigente

MIME_DOCX = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

_MESES = [
    "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
    "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE",
]

# Tipo de documento almacenado en cliente.tipo_documento (enum
# TipoIdentificacion) → sigla que usa el formato legal.
_TIPO_ID = {
    "1": "CC", "2": "NIT", "4": "CE", "5": "PAS",
    "6": "PPT", "7": "TI", "8": "DNI", "9": "PEP",
}

# El formato "Solicitud de crédito" imprime el nombre largo.
_TIPO_ID_LARGO = {
    "1": "CEDULA DE CIUDADANIA",
    "2": "NIT",
    "4": "CEDULA DE EXTRANJERIA",
    "5": "PASAPORTE",
    "6": "PERMISO POR PROTECCION TEMPORAL",
    "7": "TARJETA DE IDENTIDAD",
    "8": "DOCUMENTO NACIONAL DE IDENTIDAD",
    "9": "PERMISO ESPECIAL DE PERMANENCIA",
}

# Enums almacenados en minúscula → etiqueta del formato impreso.
_OCUPACION_LABEL = {
    "empleado": "Empleado",
    "independiente": "Independiente",
    "pensionado": "Pensionado",
    "fuerzas_militares": "Fuerzas Militares",
}
_TIPO_CONTRATO_LABEL = {
    "indefinido": "Indefinido",
    "fijo": "Fijo",
    "obra_labor": "Obra o Labor",
    "no_aplica": "No aplica",
}

_IVA = Decimal("0.19")


def _si_no(valor: bool | None) -> str:
    if valor is None:
        return ""
    return "SI" if valor else "NO"


def _fmt_pct(valor: Decimal | int | float | None) -> str:
    """5 → '5', 0.22 → '0.22' (punto decimal como en el formato real)."""
    if valor is None:
        return "0"
    return f"{Decimal(str(valor)).quantize(Decimal('0.0001')).normalize():f}"


def _fmt_fecha(valor: date | datetime | None) -> str:
    """El formato impreso usa aaaa/mm/dd."""
    if valor is None:
        return ""
    return valor.strftime("%Y/%m/%d")

# tipo evidencia → (plantilla | generador | copia, nombre de salida)
_DOCS: list[tuple[str, str, str]] = [
    ("doc_autorizacion", "autorizacion_centrales.docx", "1. Autorizacion consulta centrales - {cedula}.docx"),
    ("doc_carta_aprobacion", "carta_aprobacion.docx", "2. Carta de aprobacion - {cedula}.docx"),
    ("doc_pagare", "pagare.docx", "3. Pagare - {cedula}.docx"),
    ("doc_instrucciones", "carta_instrucciones.docx", "4. Carta de instrucciones - {cedula}.docx"),
    ("doc_prenda", "prenda.docx", "5. Prenda sin tenencia - {cedula}.docx"),
    ("doc_asegurabilidad", "__asegurabilidad__", "6. Declaracion asegurabilidad - {cedula}.docx"),
    ("doc_solicitud", "solicitud_credito.docx", "7. Solicitud de credito - {cedula}.docx"),
    ("doc_compromiso", "compromiso_cartera.docx", "8. Compromiso de pago - {cedula}.docx"),
    ("doc_amortizacion", "__amortizacion__", "9. Tabla de amortizacion - {cedula}.docx"),
]

# Soporte documental de la radicación: la autorización de consulta a
# centrales (evidencia del consentimiento Habeas Data) y la solicitud
# de crédito diligenciada. Se generan al evaluar — haya o no
# aprobación — porque la consulta al buró ya se hizo con el aval del
# cliente. Si luego firma, el paquete de legalización regenera estos
# mismos tipos ya estampados con el uuid_firma.
_DOCS_RADICACION = [d for d in _DOCS if d[0] in {"doc_autorizacion", "doc_solicitud"}]


def _fmt(valor: Decimal | int | float | None) -> str:
    """12_781_665 → '12.781.665' (formato es-CO de los formatos reales)."""
    if valor is None:
        return ""
    entero = int(Decimal(str(valor)).quantize(Decimal("1")))
    return f"{entero:,}".replace(",", ".")


def _sumar_meses(fecha: date, meses: int) -> date:
    mes = fecha.month - 1 + meses
    anio = fecha.year + mes // 12
    return date(anio, mes % 12 + 1, min(fecha.day, 28))


# Paleta de marca usada en los documentos generados (azul Pacífico).
_AZUL = "005787"
_AZUL_SUAVE = "E8F0F5"
_CEBRA = "F3F7FA"
_BORDE_SUAVE = "B7C6CF"
_TOTALES = "D8E4EC"


def _sombrear_celda(celda, fill: str) -> None:
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), fill)
    celda._tc.get_or_add_tcPr().append(shd)


def _bordes_tabla(tabla, color: str = _BORDE_SUAVE, tamano: int = 4) -> None:
    """Bordes finos de un solo color (reemplaza la rejilla negra)."""
    bordes = OxmlElement("w:tblBorders")
    for lado in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{lado}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(tamano))
        el.set(qn("w:color"), color)
        bordes.append(el)
    tabla._tbl.tblPr.append(bordes)


def _margenes_tabla(tabla, horizontal: int = 80, vertical: int = 30) -> None:
    """Aire interno en las celdas (twips: 80 ≈ 0.14 cm)."""
    mar = OxmlElement("w:tblCellMar")
    for lado, valor in (("left", horizontal), ("right", horizontal), ("top", vertical), ("bottom", vertical)):
        el = OxmlElement(f"w:{lado}")
        el.set(qn("w:w"), str(valor))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tabla._tbl.tblPr.append(mar)


def _celda(celda, texto: str, *, negrita=False, tamano=8, color=None,
           alinear=None) -> None:
    p = celda.paragraphs[0]
    if alinear is not None:
        p.alignment = alinear
    run = p.add_run(texto)
    run.bold = negrita
    run.font.size = Pt(tamano)
    if color is not None:
        run.font.color.rgb = color


def _partes_fecha(fecha: date | datetime) -> dict[str, str]:
    return {
        "DIA": str(fecha.day),
        "MES": _MESES[fecha.month - 1],
        "AÑO": str(fecha.year),
    }


def _xml_entidades(texto: str) -> str:
    """MailMerge serializa los no-ASCII como entidades (é → &#233;,
    “ → &#8220;); la copia literal conserva UTF-8. Se prueban ambas."""
    return "".join(c if ord(c) < 128 else f"&#{ord(c)};" for c in texto)


def _reemplazar_en_docx(ruta: Path, reemplazos: dict[str, str]) -> None:
    """Sustituye literales «campo» que no son MERGEFIELD (p. ej. el
    consecutivo del pagaré, que viene como texto fijo en la plantilla)."""
    temporal = ruta.with_suffix(".tmp")
    with zipfile.ZipFile(ruta) as origen, zipfile.ZipFile(
        temporal, "w", zipfile.ZIP_DEFLATED
    ) as destino:
        for item in origen.namelist():
            contenido = origen.read(item)
            if item == "word/document.xml":
                texto = contenido.decode("utf-8")
                for buscar, reemplazo in reemplazos.items():
                    texto = texto.replace(buscar, reemplazo)
                    escapado = _xml_entidades(buscar)
                    if escapado != buscar:
                        texto = texto.replace(escapado, reemplazo)
                contenido = texto.encode("utf-8")
            destino.writestr(item, contenido)
    temporal.replace(ruta)


class DocumentoService:
    """Genera el paquete de documentos legales de una solicitud firmada."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = SolicitudRepository(db)
        self.evidencias = EvidenciaRepository(db)
        self.settings = get_settings()

    # ------------------------------------------------------------------
    def generar_paquete(self, id_solicitud: uuid.UUID) -> list[DocumentoEvidencia]:
        solicitud = self.repo.obtener_detalle(id_solicitud)
        if solicitud is None:
            raise SolicitudNoEncontradaError(f"No existe la solicitud {id_solicitud}")
        if solicitud.fecha_hora_firma is None:
            # El paquete solo existe una vez el cliente firmó por OTP.
            return []
        return self._generar_docs(solicitud, _DOCS)

    def generar_paquete_radicacion(self, id_solicitud: uuid.UUID) -> list[DocumentoEvidencia]:
        """Documentos de soporte de la radicación: autorización de
        consulta a centrales y solicitud de crédito, sin firma OTP — el
        consentimiento del paso 2 respalda la consulta que ya se hizo."""
        solicitud = self.repo.obtener_detalle(id_solicitud)
        if solicitud is None:
            raise SolicitudNoEncontradaError(f"No existe la solicitud {id_solicitud}")
        return self._generar_docs(solicitud, _DOCS_RADICACION)

    def _generar_docs(
        self,
        solicitud: SolicitudCredito,
        docs: list[tuple[str, str, str]],
    ) -> list[DocumentoEvidencia]:
        campos = self._campos(solicitud)
        plantillas = Path(self.settings.documentos_plantillas_dir)
        destino_dir = (
            Path(self.settings.evidencias_dir) / "legalizacion" / str(solicitud.id_solicitud)
        )
        destino_dir.mkdir(parents=True, exist_ok=True)

        sesion = self._sesion_legalizacion(solicitud)
        generadas: list[DocumentoEvidencia] = []
        for tipo, plantilla, patron in docs:
            nombre = patron.format(cedula=solicitud.cliente.num_cedula)
            salida = destino_dir / nombre
            if plantilla == "__asegurabilidad__":
                self._generar_asegurabilidad(salida, solicitud, campos)
            elif plantilla == "__amortizacion__":
                self._generar_amortizacion(salida, solicitud, campos)
            elif plantilla in ("compromiso_cartera.docx", "solicitud_credito.docx"):
                # Sin MERGEFIELDs: se llenan por reemplazo literal.
                shutil.copyfile(plantillas / plantilla, salida)
            else:
                with MailMerge(str(plantillas / plantilla)) as doc:
                    doc.merge(**campos)
                    doc.write(str(salida))
            reemplazos = self._reemplazos_literal(plantilla, campos)
            if reemplazos:
                _reemplazar_en_docx(salida, reemplazos)
            self._estampar_firma(salida, campos)
            generadas.append(self._registrar(sesion, solicitud, tipo, salida))
        return generadas

    def _estampar_firma(self, salida: Path, campos: dict[str, str]) -> None:
        """Estampa el uuid_firma en TODOS los documentos del paquete:
        QR + texto. Es el identificador del acto de firma electrónica
        (OTP) y debe quedar visible —y verificable— en cada pieza legal.

        Si el documento tiene el bloque de firma en un cuadro de texto
        anclado a la página (la "Solicitud de crédito"), el sello va
        dentro de ese cuadro: agregarlo al final del flujo lo
        superpondría sobre el nombre del deudor."""
        uuid_firma = campos.get("FIRMA_UUID")
        if not uuid_firma:
            return
        doc = Document(str(salida))
        url_verificacion = (
            f"{self.settings.app_url_publica.rstrip('/')}"
            f"/verificar-firma/{uuid_firma}"
        )
        qr = segno.make(url_verificacion, error="m")
        buffer = io.BytesIO()
        qr.save(buffer, kind="png", scale=6, border=2)
        buffer.seek(0)
        texto = (
            "Identificador único de firma electrónica (OTP): "
            f"{uuid_firma}"
        )
        if not self._estampar_en_cuadro_firma(doc, buffer, texto):
            doc.add_paragraph().add_run().add_picture(buffer, width=Cm(2.4))
            run = doc.add_paragraph().add_run(texto)
            run.font.size = Pt(8)
        doc.save(str(salida))

    @staticmethod
    def _run_imagen(doc, origen, ancho: Cm):
        """Compone la imagen en un párrafo temporal del cuerpo
        (python-docx crea la relación) y devuelve el <w:r> reutilizable
        dentro de cuadros de texto."""
        tmp = doc.add_paragraph()
        tmp.add_run().add_picture(origen, width=ancho)
        run = tmp._p.find(qn("w:r"))
        tmp._p.getparent().remove(tmp._p)
        return run

    def _estampar_en_cuadro_firma(
        self, doc, buffer: io.BytesIO, texto: str
    ) -> bool:
        """Inyecta QR + uuid dentro del cuadro de firma (w:txbxContent
        con 'DEUDOR'). Devuelve True si había cuadro; False si el doc no
        lo tiene y el sello debe ir al final del flujo normal."""
        from copy import deepcopy

        cajas = [
            c
            for c in doc.element.findall(f".//{qn('w:txbxContent')}")
            if "DEUDOR" in "".join(c.itertext())
        ]
        if not cajas:
            return False
        run_qr = self._run_imagen(doc, buffer, Cm(2.0))
        for caja in cajas:
            p_qr = OxmlElement("w:p")
            p_qr.append(deepcopy(run_qr))
            caja.append(p_qr)
            p_txt = OxmlElement("w:p")
            r = OxmlElement("w:r")
            rpr = OxmlElement("w:rPr")
            sz = OxmlElement("w:sz")
            sz.set(qn("w:val"), "14")  # 7 pt
            rpr.append(sz)
            r.append(rpr)
            t = OxmlElement("w:t")
            t.text = texto
            r.append(t)
            p_txt.append(r)
            caja.append(p_txt)
        return True

    def _reemplazos_literal(
        self, plantilla: str, campos: dict[str, str]
    ) -> dict[str, str]:
        """Literales fijos de cada plantilla que no son MERGEFIELD y se
        sustituyen como texto plano sobre el XML del DOCX generado."""
        consecutivo = campos.get("CONSECUTIVO", "")
        if plantilla == "pagare.docx":
            reemplazos = {}
            if consecutivo:
                reemplazos["“Consecutivo”"] = consecutivo
            if campos.get("TASA"):
                # La tasa es un blanco manuscrito (________%) en la
                # plantilla, partido en tres runs del DOCX.
                reemplazos.update(
                    {
                        "<w:t>(__</w:t>": "<w:t>(</w:t>",
                        "<w:t>___</w:t>": f"<w:t>{campos['TASA']}</w:t>",
                        "<w:t>__%)</w:t>": "<w:t>%)</w:t>",
                    }
                )
            return reemplazos
        if plantilla == "carta_instrucciones.docx" and consecutivo:
            return {"No 001": f"No {consecutivo}"}
        if plantilla == "carta_aprobacion.docx":
            reemplazos = {}
            if consecutivo:
                reemplazos["XXXX"] = f"No. {consecutivo}"
            # La solicitud no guarda el asesor: nombre y celular quedan
            # en blanco para diligenciar a mano como en el formato real.
            reemplazos["NOMBRE ASESOR"] = "____________________________"
            reemplazos["NÚMERO CELULAR"] = "____________________"
            return reemplazos
        if plantilla == "compromiso_cartera.docx":
            # La plantilla venía diligenciada con datos de muestra.
            return {
                "DIANA SOFIA AYA CASTELLANOS": campos["NOMBRE_COMPLETO"],
                "28549365": campos["CÉDULA"],
            }
        if plantilla == "autorizacion_centrales.docx":
            reemplazos = {}
            if campos.get("CORREO"):
                reemplazos["Correo Electrónico Autorizado:"] = (
                    f"Correo Electrónico Autorizado: {campos['CORREO']}"
                )
            if campos.get("TELEFONO"):
                reemplazos["Teléfono Celular Autorizado:"] = (
                    f"Teléfono Celular Autorizado: {campos['TELEFONO']}"
                )
            return reemplazos
        if plantilla == "solicitud_credito.docx":
            # Tokens {{CAMPO}} insertados por scripts/generar_plantilla_solicitud.
            # Los valores van a un <w:t>: se escapan como XML.
            return {
                "{{%s}}" % nombre: _xml_escape(valor)
                for nombre, valor in campos.items()
            }
        return {}

    # ------------------------------------------------------------------
    def _campos(self, solicitud: SolicitudCredito) -> dict[str, str]:
        cliente = solicitud.cliente
        contacto = solicitud.contacto_vivienda
        oferta = next(
            (o for o in solicitud.ofertas if o.seleccionada),
            solicitud.ofertas[0] if solicitud.ofertas else None,
        )
        vehiculo = (
            self.db.query(ProductoVehiculo)
            .filter(ProductoVehiculo.id_solicitud == solicitud.id_solicitud)
            .first()
        )
        firma = (solicitud.fecha_hora_firma or datetime.now(UTC)).date()
        dia_pago = self.settings.documentos_dia_pago
        mes_siguiente = _sumar_meses(firma, 1)
        fecha_inicio = date(mes_siguiente.year, mes_siguiente.month, dia_pago)
        plazo = int(
            (oferta.plazo_ofrecido if oferta else None)
            or solicitud.plazo_deseado_meses
            or 0
        )
        fecha_fin = _sumar_meses(fecha_inicio, plazo)
        monto = oferta.monto_aprobado if oferta else None
        # La cuota del pagaré/carta es la TOTAL (anualidad + seguro de
        # vida): coincide con lo que el cliente vio en la oferta.
        credito = (
            self.db.query(CreditoFinanciacion)
            .filter(CreditoFinanciacion.id_solicitud == solicitud.id_solicitud)
            .first()
        )
        cuota = credito.cuota_total if credito else (oferta.cuota_mensual if oferta else None)
        tasa = credito.tasa if credito else (oferta.tasa_ofrecida if oferta else None)

        campos: dict[str, str] = {
            "NOMBRE_COMPLETO": cliente.nombre_completo,
            "TITULAR": cliente.nombre_completo,
            "TIPO_ID": _TIPO_ID.get(str(cliente.tipo_documento), str(cliente.tipo_documento)),
            "CÉDULA": cliente.num_cedula,
            "CIUDAD_CC": cliente.ciudad_expedicion.nombre if cliente.ciudad_expedicion else "",
            "CIUDAD_FIRMA": self.settings.documentos_ciudad_firma,
            "CIUDAD_RESIDENCIA": (
                contacto.ciudad.nombre
                if contacto and contacto.ciudad
                else (cliente.ciudad_expedicion.nombre if cliente.ciudad_expedicion else "")
            ),
            "SALDO_A_FINANCIAR": _fmt(monto),
            "SALDO_LETRAS": numero_a_letras(monto) if monto is not None else "",
            "PLAZO": str(plazo or ""),
            "CUOTA": _fmt(cuota),
            "CUOTA_LETRAS": numero_a_letras(cuota) if cuota is not None else "",
            "FECHA_INICIO": fecha_inicio.strftime("%d/%m/%Y"),
            "FECHA_FIN": fecha_fin.strftime("%d/%m/%Y"),
            "MARCA": vehiculo.marca or "" if vehiculo else "",
            "MODELO": vehiculo.modelo or "" if vehiculo else "",
            "LINEA": vehiculo.referencia or "" if vehiculo else "",
            "COLOR": vehiculo.color or "" if vehiculo else "",
            # Formato del documento real: (1.88%) — punto decimal.
            "TASA": f"{Decimal(str(tasa)).normalize():f}" if tasa is not None else "",
            "CONSECUTIVO": str(solicitud.num_solicitud or solicitud.id_solicitud)[:12],
            "CORREO": (contacto.correo or "") if contacto else "",
            "TELEFONO": (contacto.telefono or "") if contacto else "",
            "FIRMA_UUID": str(solicitud.uuid_firma or ""),
            **_partes_fecha(firma),
        }
        campos.update(
            self._campos_solicitud(solicitud, campos, oferta, credito, vehiculo, firma, plazo, tasa)
        )
        return campos

    # ------------------------------------------------------------------
    def _campos_solicitud(
        self,
        solicitud: SolicitudCredito,
        campos: dict[str, str],
        oferta: OfertaCredito | None,
        credito: CreditoFinanciacion | None,
        vehiculo: ProductoVehiculo | None,
        firma: date,
        plazo: int,
        tasa,
    ) -> dict[str, str]:
        """Tokens {{CAMPO}} del documento 7 'Solicitud de crédito':
        identidad, contacto, residencia, personal, financiero, laboral
        y la hoja de negocio que replica la composición del saldo."""
        cliente = solicitud.cliente
        contacto = solicitud.contacto_vivienda
        laboral = solicitud.datos_laborales
        ciudad_nac = cliente.ciudad_nacimiento

        # --- Hoja de negocio (misma composición que el frontend:
        #     saldo = valor neto + accesorios + matrícula + SOAT + aval) ---
        valor_moto = Decimal(str(vehiculo.valor_moto_iva or 0)) if vehiculo else Decimal(0)
        if vehiculo and vehiculo.descuento_pesos:
            # El descuento es uno solo: en pesos O en porcentaje.
            desc_valor = Decimal(str(vehiculo.descuento_pesos))
            desc_pct = desc_valor / valor_moto * 100 if valor_moto else Decimal(0)
        elif vehiculo and vehiculo.descuento_pct:
            desc_pct = Decimal(str(vehiculo.descuento_pct))
            desc_valor = valor_moto * desc_pct / 100
        else:
            desc_valor = desc_pct = Decimal(0)
        total_moto = valor_moto - desc_valor
        subtotal_moto = total_moto / (1 + _IVA)
        iva_moto = total_moto - subtotal_moto
        accesorios = Decimal(str(vehiculo.accesorios or 0)) if vehiculo else Decimal(0)
        matricula = Decimal(str(vehiculo.matricula or 0)) if vehiculo else Decimal(0)
        soat = Decimal(str(vehiculo.soat or 0)) if vehiculo else Decimal(0)
        impuestos = Decimal(str(vehiculo.impuestos or 0)) if vehiculo else Decimal(0)
        adicionales = accesorios + matricula + soat + impuestos
        cuota_inicial = Decimal(str(credito.cuota_inicial or 0)) if credito else Decimal(0)
        total_general = total_moto + adicionales - cuota_inicial
        aval_pct = Decimal(str(vehiculo.aval_pct or 0)) if vehiculo else Decimal(0)
        fondo = total_moto * aval_pct / 100
        saldo = Decimal(str(oferta.monto_aprobado or 0)) if oferta else Decimal(0)
        iva_fondo = fondo * _IVA
        gastos = saldo - total_general - fondo - iva_fondo
        if gastos < 0:
            # El saldo capturado no incluye IVA sobre el fondo: el
            # residual va a gastos administrativos para que la hoja
            # siempre cuadre con el saldo financiado real.
            iva_fondo = Decimal(0)
            gastos = saldo - total_general - fondo
        if gastos < 0:
            gastos = Decimal(0)

        # --- Cuotas y financiación (persistidas si el crédito ya se
        #     creó en el desembolso; si no, se calculan de la oferta) ---
        if credito is not None:
            cuota_fin = Decimal(str(credito.cuota_financiacion or 0))
            cuota_vida = Decimal(str(credito.cuota_seguro_vida or 0))
            cuota_total = Decimal(str(credito.cuota_total or 0))
        else:
            seguro = seguro_vida_vigente(self.db)
            prima = Decimal(str(seguro.tasa_prima)) if seguro else Decimal(0)
            cuota_fin = cuota_anualidad(
                saldo, Decimal(str(tasa or 0)), int(plazo or 0)
            ) if plazo else Decimal(0)
            cuota_vida = cuota_seguro(saldo, prima)
            # La hoja debe cuadrar internamente: la cuota total es la
            # suma de sus dos componentes, no el valor crudo de la
            # oferta (que tras re-selección guarda solo la anualidad).
            cuota_total = cuota_fin + cuota_vida
        valor_financiacion = cuota_fin * plazo - saldo
        valor_vida = cuota_vida * plazo
        total_pagar = saldo + valor_financiacion + valor_vida
        seguro_pct = cuota_vida / saldo * 100 if saldo else Decimal(0)

        # Antigüedad: meses_continuidad declarado, o calculado desde
        # fecha_ingreso a la fecha de firma.
        antiguedad = laboral.meses_continuidad if laboral else None
        if antiguedad is None and laboral and laboral.fecha_ingreso:
            delta = firma - laboral.fecha_ingreso
            antiguedad = max(0, delta.days // 30)

        return {
            # Encabezado
            "FECHA_SOLICITUD": firma.strftime("%Y/%m/%d"),
            "NUM_SOLICITUD": campos["CONSECUTIVO"],
            # Titular
            "TIPO_DOCUMENTO": _TIPO_ID_LARGO.get(
                str(cliente.tipo_documento), str(cliente.tipo_documento)
            ),
            "NUMERO_DOCUMENTO": cliente.num_cedula,
            "FECHA_EXPEDICION": _fmt_fecha(cliente.fecha_expedicion),
            "FECHA_NACIMIENTO": _fmt_fecha(cliente.fecha_nacimiento),
            "CIUDAD_EXPEDICION": (
                cliente.ciudad_expedicion.nombre if cliente.ciudad_expedicion else ""
            ),
            "CIUDAD_NACIMIENTO": ciudad_nac.nombre if ciudad_nac else "",
            "DEPARTAMENTO_NACIMIENTO": ciudad_nac.departamento if ciudad_nac else "",
            "PAIS_NACIMIENTO": (
                (ciudad_nac.pais if ciudad_nac else "") or cliente.nacionalidad or ""
            ),
            # Contacto
            "CELULAR": campos["TELEFONO"],
            "EMAIL": campos["CORREO"],
            # Residencia
            "DIRECCION": (contacto.direccion or "") if contacto else "",
            "CIUDAD_MUNICIPIO": campos["CIUDAD_RESIDENCIA"],
            "ESTRATO": str(contacto.estrato) if contacto and contacto.estrato else "",
            "BARRIO": (contacto.barrio or "") if contacto else "",
            "TIPO_VIVIENDA": (contacto.tipo_vivienda or "") if contacto else "",
            "ZONA_RURAL": _si_no(contacto.zona_rural) if contacto else "",
            # Personal
            "ESTADO_CIVIL": (contacto.estado_civil or "") if contacto else "",
            "NUM_HIJOS": (
                str(contacto.num_hijos)
                if contacto and contacto.num_hijos is not None
                else ""
            ),
            "PERSONAS_A_CARGO": (
                str(contacto.personas_a_cargo)
                if contacto and contacto.personas_a_cargo is not None
                else ""
            ),
            "CABEZA_FAMILIA": _si_no(contacto.es_cabeza_familia) if contacto else "",
            # Financiera
            "BIENES_RAICES": _si_no(contacto.cuenta_bienes_raices) if contacto else "",
            "MOTO": _si_no(contacto.tiene_moto) if contacto else "",
            "PRIMERA_MOTO": _si_no(contacto.primera_moto) if contacto else "",
            "CUENTA_VEHICULO": _si_no(contacto.cuenta_vehiculo) if contacto else "",
            "CARRO": _si_no(contacto.tiene_carro) if contacto else "",
            "ESTOY_FINANCIANDO": _si_no(contacto.estoy_financiando) if contacto else "",
            # Laboral
            "PERFIL_CLIENTE": _OCUPACION_LABEL.get(
                str(cliente.ocupacion or ""), str(cliente.ocupacion or "")
            ),
            "TIPO_CONTRATO": _TIPO_CONTRATO_LABEL.get(
                str(laboral.tipo_contrato or ""), str(laboral.tipo_contrato or "")
            ) if laboral else "",
            "FECHA_INGRESO": _fmt_fecha(laboral.fecha_ingreso) if laboral else "",
            "ANTIGUEDAD_MESES": str(antiguedad) if antiguedad is not None else "",
            "INGRESOS_MENSUAL": _fmt(laboral.ingreso_mensual) if laboral else "",
            "ANIOS_CAMARA": (
                _fmt_pct(laboral.anios_camara_comercio)
                if laboral and laboral.anios_camara_comercio is not None
                else ""
            ),
            "NOMBRE_EMPRESA": (laboral.nombre_empresa or "") if laboral else "",
            "CIUDAD_EMPRESA": (
                laboral.ciudad_empresa.nombre
                if laboral and laboral.ciudad_empresa
                else ""
            ),
            "ACTIVIDAD_COMERCIAL": (laboral.actividad_comercial or "") if laboral else "",
            "CARGO": (laboral.cargo or "") if laboral else "",
            "NIVEL_EDUCATIVO": (laboral.nivel_educativo or "") if laboral else "",
            "PROFESION": (laboral.profesion or "") if laboral else "",
            # Crédito / vehículo
            "REFERENCIA": campos["LINEA"],
            # Hoja de negocio
            "VALOR_MOTO_IVA": _fmt(valor_moto),
            "VALOR_MOTO_SIN_IVA": _fmt(valor_moto / (1 + _IVA)),
            "DESCUENTO_PCT": _fmt_pct(desc_pct),
            "DESCUENTO_VALOR": _fmt(desc_valor),
            "SUBTOTAL_MOTO": _fmt(subtotal_moto),
            "IVA_MOTO": _fmt(iva_moto),
            "TOTAL_MOTO": _fmt(total_moto),
            "MATRICULA": _fmt(matricula),
            "SOAT": _fmt(soat),
            "IMPUESTOS": _fmt(impuestos),
            "ACCESORIOS": _fmt(accesorios),
            "TOTAL_ADICIONALES": _fmt(adicionales),
            "CUOTA_INICIAL_PCT": "0",
            "CUOTA_INICIAL": _fmt(cuota_inicial),
            "TOTAL_GENERAL": _fmt(total_general),
            "FONDO_GARANTIA_PCT": _fmt_pct(aval_pct),
            "FONDO_GARANTIA": _fmt(fondo),
            "IVA_FONDO": _fmt(iva_fondo),
            "GASTOS_ADMINISTRATIVOS": _fmt(gastos),
            "VALOR_FINANCIACION": _fmt(valor_financiacion),
            "SEGURO_VIDA_PCT": _fmt_pct(seguro_pct),
            "VALOR_SEGURO_VIDA": _fmt(valor_vida),
            "TOTAL_A_PAGAR": _fmt(total_pagar),
            "CUOTA_FINANCIACION": _fmt(cuota_fin),
            "CUOTA_SEGURO_VIDA": _fmt(cuota_vida),
            "CUOTA_TOTAL": _fmt(cuota_total),
        }

    # ------------------------------------------------------------------
    def _sesion_legalizacion(self, solicitud: SolicitudCredito) -> SesionCaptura:
        """documento_evidencia exige id_sesion: la sesión 'legalizacion'
        es el sobre que agrupa los documentos generados del paquete."""
        sesion = (
            self.db.query(SesionCaptura)
            .filter(
                SesionCaptura.id_solicitud == solicitud.id_solicitud,
                SesionCaptura.estado == "legalizacion",
            )
            .first()
        )
        if sesion is not None:
            return sesion
        sesion = SesionCaptura(
            token=secrets.token_urlsafe(32),
            estado="legalizacion",
            id_solicitud=solicitud.id_solicitud,
            expira_en=datetime.now(UTC) + timedelta(days=3650),
        )
        return self.evidencias.crear_sesion(sesion)

    def _registrar(
        self,
        sesion: SesionCaptura,
        solicitud: SolicitudCredito,
        tipo: str,
        salida: Path,
    ) -> DocumentoEvidencia:
        contenido = salida.read_bytes()
        ruta_relativa = str(salida.relative_to(self.settings.evidencias_dir))
        evidencia = DocumentoEvidencia(
            id_sesion=sesion.id_sesion,
            id_solicitud=solicitud.id_solicitud,
            tipo=tipo,
            ruta=ruta_relativa,
            nombre_original=salida.name,
            mime=MIME_DOCX,
            tamano_bytes=len(contenido),
            hash_sha256=hashlib.sha256(contenido).hexdigest(),
        )
        ruta_previa = self.evidencias.reemplazar_evidencia(
            sesion.id_sesion, tipo, evidencia
        )
        # Al regenerar, la ruta nueva es la misma que la previa; solo se
        # limpia el archivo viejo cuando el nombre efectivamente cambió.
        if ruta_previa and ruta_previa != ruta_relativa:
            (Path(self.settings.evidencias_dir) / ruta_previa).unlink(missing_ok=True)
        return evidencia

    # ------------------------------------------------------------------
    def _generar_asegurabilidad(
        self, salida: Path, solicitud: SolicitudCredito, campos: dict[str, str]
    ) -> None:
        """Doc 6: la plantilla fuente es .doc binario; se reconstruye en
        DOCX con el mismo texto legal y los datos de la solicitud."""
        cliente = solicitud.cliente
        nac = cliente.fecha_nacimiento
        firma = (solicitud.fecha_hora_firma or datetime.now(UTC)).date()
        doc = Document()
        doc.add_heading("DECLARACION DE ASEGURABILIDAD", level=2)
        p = doc.add_paragraph()
        p.add_run("SEGURO DE VIDA PARA DEUDORES").bold = True
        p = doc.add_paragraph()
        run = p.add_run(
            "IMPORTANTE: NO FIRME SIN ANTES LEER Y ENTENDER EL CONTENIDO DE "
            "ESTE DOCUMENTO, SI USTED FALTA A LA VERDAD AL SUSCRIBIR LA "
            "SIGUIENTE DECLARACION, EL SEGURO QUEDARA ANULADO (ARTICULO "
            "1058 Y 1158 DEL CODIGO DE COMERCIO)"
        )
        run.bold = True
        doc.add_paragraph(
            f"YO {campos['NOMBRE_COMPLETO']} MAYOR DE EDAD, IDENTIFICADO COMO "
            f"APARECE AL PIE DE MI FIRMA, DOMICILIADO EN {campos['CIUDAD_RESIDENCIA']}, "
            f"NACIDO EL DIA {nac.day} DE {_MESES[nac.month - 1]} DEL AÑO {nac.year}, "
            "DECLARO QUE:"
        )
        doc.add_paragraph(
            "MI ESTADO DE SALUD ES NORMAL, NO PADEZCO NI HE PADECIDO ENFERMEDADES "
            "TALES COMO: ENFERMEDADES CONGÉNITAS, AFECCIONES CARDIOVASCULARES, "
            "HIV-SIDA, HIPERTENSION ARTERIAL, CANCER, DIABETES, HEPATITIS B, "
            "CIRROSIS, INSUFICIENCIA RENAL Y SIMILARES CONSIDERADAS GRAVES Y EN LA "
            "ACTUALIDAD NO SUFRO DE ENFERMEDADES CRÓNICAS QUE INCIDAN SOBRE MI "
            "ESTADO DE SALUD."
        )
        doc.add_paragraph(
            "REITERO QUE LO MANIFESTADO EN ESTA DECLARACION ES VERIDICO Y QUE "
            "TENGO CONOCIMIENTO QUE EN CUALQUIER FALTA A LA VERDAD ES CAUSAL DE "
            "NULIDAD DE ESTE SEGURO. DE CONFORMIDAD CON LO ESTIPULADO EN EL "
            "ARTICULO 31 DE LA LEY 23 DE 1981, AUTORIZO EXPRESAMENTE A LA "
            "COMPAÑÍA DE SEGUROS PARA TENER ACCESO A MI HISTORIA CLINICA Y A "
            "TODOS AQUELLOS DATOS QUE EN ELLA SE REGISTREN O LLEGUEN A SER "
            "REGISTRADOS Y A OBTENER COPIA DE ESE DOCUMENTO Y DE SUS ANEXOS. LA "
            "ASEGURADORA SE RESERVA TODOS LOS DERECHOS QUE PUEDAN ASISTIRLE EN "
            "CASO DE QUE ANTES O DESPUÉS DE MI FALLECIMIENTO SE COMPRUEBE QUE "
            "ESTA DECLARACIÓN NO CORRESPONDIA A LA VERDAD EN EL MOMENTO DE "
            "SOLICITAR EL SEGURO."
        )
        doc.add_paragraph(
            "EN CASO DE PADECER ALGUNA ENFERMEDAD: "
            "________________________________________________"
        )
        doc.add_paragraph(
            "LA INDEMNIZACION DE ESTE SEGURO ES SOBRE EL SALDO INSOLUTO DE LA DEUDA."
        )
        doc.add_paragraph(
            f"EN CONSTANCIA DE LO ANTERIOR, SE FIRMA EN {campos['CIUDAD_FIRMA']}, "
            f"A LOS {campos['DIA']} DIAS DE {campos['MES']} DEL AÑO {campos['AÑO']}."
        )
        doc.add_paragraph("DEUDOR")
        doc.add_paragraph("Firma:")
        doc.add_paragraph(campos["NOMBRE_COMPLETO"])
        doc.add_paragraph(f"{campos['TIPO_ID']} {campos['CÉDULA']}")
        doc.save(str(salida))

    def _generar_amortizacion(
        self, salida: Path, solicitud: SolicitudCredito, campos: dict[str, str]
    ) -> None:
        """Doc 9: tabla de amortización francesa del crédito — saldo,
        tasa y plazo reales (del crédito persistido o de la oferta
        seleccionada), con la misma fórmula de finanzas."""
        cliente = solicitud.cliente
        oferta = next(
            (o for o in solicitud.ofertas if o.seleccionada),
            solicitud.ofertas[0] if solicitud.ofertas else None,
        )
        credito = (
            self.db.query(CreditoFinanciacion)
            .filter(CreditoFinanciacion.id_solicitud == solicitud.id_solicitud)
            .first()
        )
        firma = (solicitud.fecha_hora_firma or datetime.now(UTC)).date()
        dia_pago = self.settings.documentos_dia_pago
        mes_siguiente = _sumar_meses(firma, 1)
        fecha_inicio = date(mes_siguiente.year, mes_siguiente.month, dia_pago)

        saldo = Decimal(str(credito.saldo_financiar)) if credito else (
            Decimal(str(oferta.monto_aprobado))
            if oferta and oferta.monto_aprobado is not None
            else Decimal(0)
        )
        tasa = Decimal(
            str(credito.tasa if credito else (oferta.tasa_ofrecida or 0) if oferta else 0)
        )
        plazo = int(
            credito.plazo
            if credito
            else (oferta.plazo_ofrecido or solicitud.plazo_deseado_meses or 0)
            if oferta
            else (solicitud.plazo_deseado_meses or 0)
        )
        if credito is not None:
            cuota_fin = Decimal(str(credito.cuota_financiacion or 0))
            cuota_vida = Decimal(str(credito.cuota_seguro_vida or 0))
        else:
            seguro = seguro_vida_vigente(self.db)
            prima = Decimal(str(seguro.tasa_prima)) if seguro else Decimal(0)
            cuota_fin = cuota_anualidad(saldo, tasa, plazo)
            cuota_vida = cuota_seguro(saldo, prima)
        cuota_total = cuota_fin + cuota_vida

        doc = Document()
        seccion = doc.sections[0]
        seccion.orientation = WD_ORIENT.LANDSCAPE
        seccion.page_width, seccion.page_height = (
            seccion.page_height,
            seccion.page_width,
        )
        seccion.left_margin = seccion.right_margin = Cm(1.4)
        seccion.top_margin = seccion.bottom_margin = Cm(1.4)

        # Banda de título azul Pacífico.
        banda = doc.add_paragraph()
        banda.paragraph_format.space_after = Pt(10)
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:fill"), _AZUL)
        banda._p.get_or_add_pPr().append(shd)
        run = banda.add_run("  TABLA DE AMORTIZACIÓN")
        run.bold = True
        run.font.size = Pt(13)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        run = banda.add_run(
            f"   INVERSIONES PACIFICO S.A. — {firma.strftime('%d/%m/%Y')}"
        )
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0xD5, 0xE5, 0xEF)

        # Tarjeta-resumen: etiqueta | valor × 2 columnas.
        resumen = [
            ("Cliente", campos["NOMBRE_COMPLETO"],
             "Saldo a financiar", f"$ {_fmt(saldo)}"),
            ("Documento", f"{campos['TIPO_ID']} {campos['CÉDULA']}",
             "Tasa", f"{_fmt_pct(tasa)}% mensual"),
            ("Solicitud", f"N.º {campos['CONSECUTIVO']}",
             "Plazo", f"{plazo} meses"),
            ("Cuota financiación", f"$ {_fmt(cuota_fin)}",
             "Seguro de vida", f"$ {_fmt(cuota_vida)}"),
            ("Cuota total", f"$ {_fmt(cuota_total)}",
             "Primera cuota", fecha_inicio.strftime("%d/%m/%Y")),
        ]
        card = doc.add_table(rows=len(resumen), cols=4)
        card.autofit = False
        _bordes_tabla(card)
        _margenes_tabla(card)
        for fila, (e1, v1, e2, v2) in zip(card.rows, resumen):
            _sombrear_celda(fila.cells[0], _AZUL_SUAVE)
            _sombrear_celda(fila.cells[2], _AZUL_SUAVE)
            _celda(fila.cells[0], e1, negrita=True, color=RGBColor(0x00, 0x57, 0x87))
            _celda(fila.cells[1], v1)
            _celda(fila.cells[2], e2, negrita=True, color=RGBColor(0x00, 0x57, 0x87))
            _celda(fila.cells[3], v2)
        for i, w in enumerate((Cm(4.6), Cm(8.4), Cm(4.6), Cm(8.0))):
            for fila in card.rows:
                fila.cells[i].width = w

        doc.add_paragraph()  # respiro entre tarjeta y tabla

        encabezados = [
            "N.º", "Fecha", "Saldo inicial", "Cuota", "Interés",
            "Abono a capital", "Seguro de vida", "Cuota total", "Saldo final",
        ]
        tabla = doc.add_table(rows=1, cols=len(encabezados))
        tabla.autofit = False
        _bordes_tabla(tabla)
        _margenes_tabla(tabla)
        blanco = RGBColor(0xFF, 0xFF, 0xFF)
        for i, (celda, texto) in enumerate(zip(tabla.rows[0].cells, encabezados)):
            _sombrear_celda(celda, _AZUL)
            _celda(
                celda, texto, negrita=True, color=blanco,
                alinear=WD_ALIGN_PARAGRAPH.CENTER
                if i < 2 else WD_ALIGN_PARAGRAPH.RIGHT,
            )

        saldo_corriente = saldo
        totales = [Decimal(0)] * 4  # cuota, interés, capital, seguro
        for n in range(1, plazo + 1):
            interes = saldo_corriente * tasa / 100
            capital = cuota_fin - interes
            saldo_final = saldo_corriente - capital
            if n == plazo:
                # Última cuota: ajuste por redondeo acumulado.
                capital = saldo_corriente
                cuota_fin_n = capital + interes
                saldo_final = Decimal(0)
            else:
                cuota_fin_n = cuota_fin
            fila = tabla.add_row().cells
            valores = [
                str(n),
                _sumar_meses(fecha_inicio, n - 1).strftime("%d/%m/%Y"),
                _fmt(saldo_corriente),
                _fmt(cuota_fin_n),
                _fmt(interes),
                _fmt(capital),
                _fmt(cuota_vida),
                _fmt(cuota_fin_n + cuota_vida),
                _fmt(saldo_final),
            ]
            for i, (celda, texto) in enumerate(zip(fila, valores)):
                _celda(
                    celda, texto,
                    alinear=WD_ALIGN_PARAGRAPH.CENTER
                    if i < 2 else WD_ALIGN_PARAGRAPH.RIGHT,
                )
                if n % 2 == 0:
                    _sombrear_celda(celda, _CEBRA)
            saldo_corriente = saldo_final
            totales[0] += cuota_fin_n
            totales[1] += interes
            totales[2] += capital
            totales[3] += cuota_vida

        fila = tabla.add_row().cells
        totales_txt = [
            "", "TOTALES", "", _fmt(totales[0]), _fmt(totales[1]),
            _fmt(totales[2]), _fmt(totales[3]),
            _fmt(totales[0] + totales[3]), "",
        ]
        for i, (celda, texto) in enumerate(zip(fila, totales_txt)):
            _sombrear_celda(celda, _TOTALES)
            _celda(
                celda, texto, negrita=True,
                alinear=WD_ALIGN_PARAGRAPH.CENTER
                if i < 2 else WD_ALIGN_PARAGRAPH.RIGHT,
            )

        anchos = [1.5, 2.4, 3.2, 3.0, 2.7, 3.2, 2.7, 3.0, 3.2]
        for i, w in enumerate(anchos):
            for fila in tabla.rows:
                fila.cells[i].width = Cm(w)

        nota = doc.add_paragraph()
        nota.paragraph_format.space_before = Pt(8)
        run = nota.add_run(
            "Valores en pesos colombianos (COP). Sistema francés de cuota "
            f"fija mensual con vencimiento el día {dia_pago} de cada mes; "
            "la última cuota ajusta el redondeo acumulado. El seguro de "
            "vida se paga junto con la cuota de financiación."
        )
        run.font.size = Pt(7.5)
        run.font.color.rgb = RGBColor(0x64, 0x74, 0x80)
        doc.save(str(salida))
