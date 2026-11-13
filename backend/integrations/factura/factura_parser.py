"""Parser de la factura del vehículo (PDF) emitida por el concesionario.

La factura la emite el DMS del concesionario tras la firma del pagaré.
No hay API ni formato único: cada DMS imprime su propio layout, así que
la extracción se hace por parsers en cadena — `_PARSERS` es la tupla de
funciones `parser(texto) -> DatosFactura | None` y gana el primero que
reconoce el layout. Sumar un formato nuevo de DMS es agregar una función
aquí, sin tocar el servicio.

Solo se procesa `application/pdf` con capa de texto (pypdf): un escaneo
o una imagen se acepta igual como soporte, pero devuelve None y queda
para revisión manual.
"""

from __future__ import annotations

import io
import logging
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from decimal import Decimal

logger = logging.getLogger(__name__)


@dataclass
class DatosFactura:
    """Lo que la factura dice, normalizado. `formato` identifica el
    parser que la reconoció (trazabilidad para nuevos layouts)."""

    formato: str
    numero_factura: str | None = None
    nit_comprador: str | None = None
    nombre_comprador: str | None = None
    marca: str | None = None
    linea: str | None = None
    referencia: str | None = None
    anio: str | None = None
    color: str | None = None
    numero_motor: str | None = None
    numero_chasis: str | None = None
    vin: str | None = None
    cilindraje: str | None = None
    total: Decimal | None = None
    advertencias: list[str] = field(default_factory=list)

    def como_dict(self) -> dict:
        datos = asdict(self)
        datos["total"] = str(self.total) if self.total is not None else None
        return datos


# ---------------------------------------------------------------------------
# Extracción de texto
# ---------------------------------------------------------------------------

def extraer_texto_pdf(contenido: bytes) -> str | None:
    """Texto de todas las páginas. None si el archivo está dañado, va
    clavado (contraseña) o es un escaneo sin capa de texto."""
    from pypdf import PdfReader

    try:
        lector = PdfReader(io.BytesIO(contenido))
        if lector.is_encrypted:
            return None
        partes = [(pagina.extract_text() or "") for pagina in lector.pages]
    except Exception:  # noqa: BLE001 — PDF roto/es corrupto, no importa cuál
        logger.info("No se pudo leer el PDF de la factura", exc_info=True)
        return None
    texto = "\n".join(partes).strip()
    return texto or None


# ---------------------------------------------------------------------------
# Helpers compartidos por los parsers
# ---------------------------------------------------------------------------

def solo_digitos(valor: str | None) -> str:
    """NIT/cédula sin guiones ni dígito de verificación."""
    return re.sub(r"\D", "", valor or "")


def _norm_texto(valor: str) -> str:
    """Mayúsculas sin tildes, espacios colapsados."""
    base = unicodedata.normalize("NFKD", valor or "")
    sin_tildes = "".join(c for c in base if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sin_tildes).strip().upper()


def nombres_coinciden(a: str | None, b: str | None) -> bool | None:
    """Los tokens normalizados de un nombre son subconjunto del otro, en
    cualquier dirección: la factura puede traer menos apellidos que la
    solicitud (o al revés). None si falta alguno — no se puede decidir."""
    if not a or not b:
        return None
    ta = {t for t in _norm_texto(a).split(" ") if t}
    tb = {t for t in _norm_texto(b).split(" ") if t}
    if not ta or not tb:
        return None
    return ta <= tb or tb <= ta


def _numero(texto: str) -> Decimal | None:
    """Monto con separadores de miles/decimal. Soporta es-CO
    ('4.865.000,00') y en-US ('5,453,781.51') — el formato que usa cada
    DMS varía; se decide por el último separador presente."""
    limpio = re.sub(r"[^\d,\.\-]", "", texto or "")
    if not limpio:
        return None
    try:
        if "," in limpio and "." in limpio:
            if limpio.rfind(",") > limpio.rfind("."):
                # es-CO: punto=miles, coma=decimal
                limpio = limpio.replace(".", "").replace(",", ".")
            else:
                # en-US: coma=miles, punto=decimal
                limpio = limpio.replace(",", "")
        elif "," in limpio:
            limpio = (
                limpio.replace(",", ".")
                if re.search(r",\d{1,2}$", limpio)
                else limpio.replace(",", "")
            )
        elif re.fullmatch(r"\d{1,3}(\.\d{3})+", limpio):
            limpio = limpio.replace(".", "")
        return Decimal(limpio)
    except ArithmeticError:
        return None


_VIN_RE = re.compile(r"\b([A-HJ-NPR-Z0-9]{17})\b")


# ---------------------------------------------------------------------------
# Parser `dms_motos`: reporte d_factura_veh "FACTURAS DE VENTA DE MOTOS"
# del DMS de concesionarios de motos.
# ---------------------------------------------------------------------------

def _parser_dms_motos(texto: str) -> DatosFactura | None:
    if "VENDIDO A" not in texto or not re.search(r"VIN\s*\n\s*MOTOR", texto):
        return None
    datos = DatosFactura(formato="dms_motos")

    # --- Comprador: "VENDIDO A\nNOMBRE <nit>"; el NIT es el primer
    #     tramo de 5-12 dígitos tras el nombre. ---
    m = re.search(
        r"VENDIDO A\s*\n+([^\n]*?\b(\d{5,12})\b[^\n]*)",
        texto,
    )
    if m:
        linea = m.group(1).strip()
        nit = m.group(2)
        datos.nit_comprador = nit
        datos.nombre_comprador = (
            re.sub(r"\s+", " ", linea[: linea.find(nit)]).strip() or None
        )

    # --- Número: "Con Prefijo: X" + la línea numérica previa a la
    #     fecha dd-mmm.-yyyy → "PREFIJO-NNNN" (sin ceros a la izquierda).
    prefijo = None
    m = re.search(r"Con\s+Prefijo\s*:?\s*([A-Z0-9-]+)", texto, re.IGNORECASE)
    if m:
        prefijo = m.group(1)
    m = re.search(
        r"(\d{1,7})\s*\n\s*\d{1,2}-[A-Za-z]{3}\.?\s*-?\s*\d{4}", texto
    )
    consecutivo = int(m.group(1)) if m else None
    if prefijo is not None and consecutivo is not None:
        datos.numero_factura = f"{prefijo}-{consecutivo}"
    elif prefijo is not None:
        datos.numero_factura = prefijo

    # --- Vehículo: "DESCRIPCIÓN <año> <marca> <línea> <referencia>"
    #     (o el bloque MARCA/LINEA/MODELO en líneas separadas). ---
    m = re.search(
        r"DESCRIPCI[OÓ]N\s+(\d{4})\s+([A-Z0-9]+)\s+([A-Z0-9][^\n]*)",
        texto,
    )
    if m:
        datos.anio = m.group(1)
        datos.marca = m.group(2)
        datos.linea = re.sub(r"\s+", " ", m.group(3)).strip()
    else:
        m = re.search(
            r"MARCA\s*\n+([^\n]+)\n+LINEA\s*\n+([^\n]+)\n+MODELO\s*\n+([^\n]+)",
            texto,
        )
        if m:
            datos.marca, datos.linea, datos.anio = (
                m.group(1).strip(),
                m.group(2).strip(),
                m.group(3).strip(),
            )

    # --- Identificación: VIN = token de 17 chars antes de la etiqueta
    #     VIN; motor = el alfanumérico inmediatamente anterior; chasis =
    #     token de 17 en el bloque SERVICIO (en moto nueva chasis = VIN);
    #     color y año del mismo bloque; cilindraje "NNN CILINDRAJE";
    #     total = último monto del bloque "TOTAL NETO". ---
    m = re.search(r"([A-HJ-NPR-Z0-9]{17})\s*\n\s*VIN\s*\n\s*MOTOR", texto)
    if m:
        datos.vin = m.group(1)
        antes = texto[: m.start(1)].rstrip()
        m2 = re.search(r"([A-Z0-9-]{6,})\s*$", antes)
        if m2:
            datos.numero_motor = m2.group(1)
    m = re.search(r"SERVICIO[^\n]*\n(?:[^\n]*\n){0,4}?\s*([A-HJ-NPR-Z0-9]{17})\b", texto)
    if m:
        datos.numero_chasis = m.group(1)
    m = re.search(r"\b(\d{2,4})\s*CILINDRAJE\b", texto)
    if m:
        datos.cilindraje = m.group(1)
    m = re.search(r"TOTAL\s+NETO[^\n]*([\d\.,]+)", texto)
    if m:
        datos.total = _numero(m.group(1))

    # Color/año del bloque SERVICIO si no salieron de DESCRIPCIÓN.
    if datos.color is None or datos.anio is None:
        m = re.search(
            r"SERVICIO[^\n]*\n(?:[^\n]*\n){0,4}?\s*([A-ZÁÉÍÓÚÑ ]{3,30})\s+(\d{4})\b",
            texto,
        )
        if m:
            datos.color = datos.color or m.group(1).strip()
            datos.anio = datos.anio or m.group(2)

    # La referencia compacta (p. ej. AK125NKD): token de la línea del
    # vehículo que contiene letras+dígitos sin espacios.
    if datos.linea:
        for tok in datos.linea.split():
            if re.search(r"[A-Z]", tok) and re.search(r"\d", tok) and len(tok) >= 5:
                datos.referencia = tok
                break

    # El formato solo se da por reconocido si trae VIN o motor (los
    # datos mínimos de la prenda); si no, None.
    if not (datos.vin or datos.numero_motor):
        return None
    return datos


# ---------------------------------------------------------------------------
# Parser `sumoto`: factura electrónica propia de SUMOTO S.A. (emitida al
# cliente cuando el aliado paga la moto al concesionario). Layout real:
# comprador + "Cédula de ciudadanía" arriba a la izquierda, número
# "MTEC NNNN" arriba a la derecha, VIN+marca+color en una línea, motor
# partido en dos líneas ("ZS154FMI-" / "38V102908"), referencia
# "AK125FLEX-2027", columna de totales a la derecha y la RESOLUCION DIAN
# al pie. Los montos vienen en formato en-US.
# ---------------------------------------------------------------------------

def _parser_sumoto(texto: str) -> DatosFactura | None:
    # Detección: la resolución DIAN del rango MTEC + la línea "Cédula de
    # ciudadanía" del comprador (se busca sin la tilde inicial por si el
    # PDF la extrae con otra codificación).
    if "RESOLUCION DIAN" not in texto or "dula de ciudadan" not in texto:
        return None
    datos = DatosFactura(formato="sumoto")

    # --- Comprador: la línea previa a "Cédula de ciudadanía NNN". ---
    m = re.search(
        r"([^\n]{3,})\n+\s*\S*dula de ciudadan\S*\s*(\d{5,12})", texto
    )
    if m:
        datos.nombre_comprador = m.group(1).strip()
        datos.nit_comprador = m.group(2)

    # --- Número: primer "MTEC NNNN" del documento (los rangos de la
    #     resolución "DEL MTEC n AL MTEC n" vienen después). ---
    m = re.search(r"\b(MTEC)\s*[- ]?\s*(\d{1,7})\b", texto)
    if m:
        datos.numero_factura = f"{m.group(1)}-{int(m.group(2))}"

    # --- VIN + marca + color: "9F2C91252V5009278   AKT   GRIS MATE". ---
    m = re.search(
        r"\b([A-HJ-NPR-Z0-9]{17})\s+([A-Z]{2,10})\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ ]{1,25})",
        texto,
    )
    if m:
        datos.vin = datos.numero_chasis = m.group(1)
        datos.marca = m.group(2)
        datos.color = re.sub(r"\s+", " ", m.group(3)).strip()

    # --- Motor: "ZS154FMI-" y su resto en la línea siguiente. ---
    m = re.search(r"\b([A-Z0-9]{4,}-)\s*\n\s*([A-Z0-9]{4,})\b", texto)
    if m:
        datos.numero_motor = m.group(1) + m.group(2)
    else:
        m = re.search(r"\b([A-Z]{2}[A-Z0-9]{3,}-[A-Z0-9]{4,})\b", texto)
        if m:
            datos.numero_motor = m.group(1)

    # --- Referencia: "AK125FLEX-2027" (lleva el año integrado). ---
    m = re.search(r"([A-Z]{2}\d{2,}[A-Z]*-\d{4})", texto)
    if m:
        datos.referencia = m.group(1)

    # --- Año y cilindraje: línea "2027 124" o el año de la referencia. ---
    m = re.search(r"^\s*(\d{4})\s+(\d{2,4})\s*$", texto, re.MULTILINE)
    if m:
        datos.anio = m.group(1)
        datos.cilindraje = m.group(2)
    if datos.anio is None and datos.referencia:
        datos.anio = datos.referencia.rsplit("-", 1)[-1]

    # --- Total: el mayor monto con decimales del documento (la factura
    #     total es el mayor valor de la columna de totales). ---
    montos = [
        _numero(tok) for tok in re.findall(r"\d{1,3}(?:[,.]\d{3})+[,.]\d{2}", texto)
    ]
    montos = [m for m in montos if m is not None]
    if montos:
        datos.total = max(montos)

    # Reconocido solo si trae VIN o motor (los mínimos de la prenda).
    if not (datos.vin or datos.numero_motor):
        return None
    return datos


_PARSERS = (_parser_dms_motos, _parser_sumoto)


def extraer_y_parsear(contenido: bytes, mime: str) -> DatosFactura | None:
    """Extrae el texto del PDF y le aplica los parsers en cadena.

    None cuando no es PDF, cuando el PDF no tiene capa de texto o cuando
    ningún parser reconoció el layout — la factura se acepta igual en el
    servicio, pero con advertencia de revisión manual.
    """
    if (mime or "").split(";")[0].strip().lower() != "application/pdf":
        return None
    texto = extraer_texto_pdf(contenido)
    if not texto:
        return None
    for parser in _PARSERS:
        datos = parser(texto)
        if datos is not None:
            return datos
    return None
