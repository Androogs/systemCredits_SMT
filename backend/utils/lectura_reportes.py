"""
Lectura de reportes de Experian exportados como JSON o como PDF que
contiene el JSON impreso (muestras del portal). El contenido se
procesa en memoria; no se guarda en disco.
"""

import json
import re
from io import BytesIO
from pathlib import Path
from typing import Any

from backend.services.motor_exceptions import ValidacionError

# Encabezados / pies que el navegador agrega al imprimir el JSON en PDF.
_LINEAS_RUIDO_PDF = (
    re.compile(r"^Dar formato al texto"),
    re.compile(r"^\d{1,2}/\d{1,2}/\d{2},.*integrityvue\.portalintegrity\.cloud"),
    re.compile(r"^https://integrityvue\."),
)


def _leer_pdf_json_bytes(contenido: bytes, nombre: str) -> dict[str, Any]:
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError as exc:
        raise ValidacionError("Para leer archivos PDF instala la dependencia: pip install pypdf") from exc
    try:
        reader = PdfReader(BytesIO(contenido))
        lineas = [linea for pagina in reader.pages for linea in (pagina.extract_text() or "").splitlines()]
    except Exception as exc:  # pypdf lanza varios tipos según el archivo
        raise ValidacionError(f"No se pudo extraer texto del PDF {nombre}: {exc}") from exc

    lineas = [linea for linea in lineas if not any(p.match(linea) for p in _LINEAS_RUIDO_PDF)]
    texto = "\n".join(lineas).strip()
    try:
        data = json.loads(texto)
    except json.JSONDecodeError as exc:
        raise ValidacionError(
            f"El PDF {nombre} no contiene un JSON completo legible (línea {exc.lineno}). "
            "Usa el JSON original descargado de Experian."
        ) from exc
    if not isinstance(data, dict):
        raise ValidacionError(f"El contenido extraído de {nombre} debe ser un objeto JSON.")
    return data


def leer_reporte_bytes(contenido: bytes, nombre: str) -> dict[str, Any]:
    """Lee un reporte JSON o PDF recibido como bytes."""
    if Path(nombre).suffix.lower() == ".pdf":
        return _leer_pdf_json_bytes(contenido, nombre)
    try:
        data = json.loads(contenido.decode("utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValidacionError(f"JSON inválido en {nombre}, línea {exc.lineno}: {exc.msg}") from exc
    except UnicodeDecodeError as exc:
        raise ValidacionError(f"El archivo {nombre} no está codificado como UTF-8.") from exc
    if not isinstance(data, dict):
        raise ValidacionError(f"El archivo {nombre} debe contener un objeto JSON.")
    return data


def leer_reporte(path: Path) -> dict[str, Any]:
    try:
        return leer_reporte_bytes(path.read_bytes(), str(path))
    except OSError as exc:
        raise ValidacionError(f"No se pudo leer {path}: {exc}") from exc
