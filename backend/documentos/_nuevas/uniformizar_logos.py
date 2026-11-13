# -*- coding: utf-8 -*-
"""Uniforma el logo Sumoto de las plantillas activas.

El visor del frontend (docx-preview) no soporta imágenes VML ni el
recorte <a:srcRect> de DrawingML: el logo se veía pequeño o invisible
en la vista previa aunque el .docx descargado se veía bien.

Este paso reemplaza cada logo del encabezado/cuerpo por un DrawingML
moderno con la banda ya recortada (logo_sumoto_banner.png, 2250x270),
así Word y la vista previa muestran lo mismo.

Se corre al final del pipeline de plantillas:

    python backend/documentos/_nuevas/swap.py
    python backend/documentos/_nuevas/swap_extra.py
    python scripts/generar_plantilla_solicitud.py
    python backend/documentos/_nuevas/uniformizar_logos.py
"""
import zipfile
import shutil
import re
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Cm

BASE = Path(__file__).parent.parent          # backend/documentos/
PLANTILLAS = BASE / "plantillas"
BANNER = BASE / "logo_sumoto_banner.png"
ANCHO = Cm(12)

V = "{urn:schemas-microsoft-com:vml}"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _run_contenedor(el):
    """Sube hasta el <w:r> que envuelve el elemento dado."""
    nodo = el
    while nodo is not None and nodo.tag != qn("w:r"):
        nodo = nodo.getparent()
    return nodo


def _reemplazar_logos_en_parrafos(parrafos, doc_parte):
    """Sustituye logos VML y DrawingML por el banner precortado.

    Devuelve cuántos logos reemplazó."""
    n = 0
    for p in parrafos:
        # Logo DrawingML primero: el dibujo grande de la cabecera (ancho
        # >= ~120pt, alto >= ~20pt). Los demás dibujos (líneas, fotos) no
        # se tocan.
        for drawing in p._p.findall(".//" + qn("w:drawing")):
            extent = drawing.find(".//" + qn("wp:extent"))
            if extent is None:
                continue
            cx, cy = int(extent.get("cx")), int(extent.get("cy"))
            if cx < 1_500_000 or cy < 250_000:
                continue
            run = _run_contenedor(drawing)
            if run is not None:
                run.getparent().remove(run)
                p.add_run().add_picture(str(BANNER), width=ANCHO)
                n += 1
                break
        # Logo VML: <w:pict><v:shape ...> sin position:absolute. No se
        # reemplaza si el párrafo ya recibió el banner en este pase.
        if n and len(p._p.findall(".//" + qn("w:drawing"))):
            continue
        for pict in p._p.findall(".//" + qn("w:pict")):
            shape = pict.find(V + "shape")
            if shape is None or "position:absolute" in (shape.get("style") or ""):
                continue
            run = _run_contenedor(pict)
            if run is not None:
                run.getparent().remove(run)
                p.add_run().add_picture(str(BANNER), width=ANCHO)
                n += 1
                break
    return n


def uniformizar(ruta: Path) -> int:
    doc = Document(str(ruta))
    n = _reemplazar_logos_en_parrafos(doc.paragraphs, doc.part)
    for seccion in doc.sections:
        header = seccion.header
        if header is not None:
            n += _reemplazar_logos_en_parrafos(header.paragraphs, header.part)
    if n:
        doc.save(str(ruta))
    return n


def main() -> None:
    for ruta in sorted(PLANTILLAS.glob("*.docx")):
        n = uniformizar(ruta)
        print(f"{ruta.name}: {n} logo(s) uniformado(s)")


if __name__ == "__main__":
    main()
