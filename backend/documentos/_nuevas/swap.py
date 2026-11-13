# -*- coding: utf-8 -*-
"""Prepara los formatos Sumoto como plantillas activas.

1. Normaliza los marcadores «CAMPO» (los fusiona en un solo run para
   que el reemplazo literal del servicio los encuentre).
2. Inyecta marcadores en los blancos: prenda (tabla vehículo),
   pagaré (tasa), políticas (titular/crédito).
3. Copia a plantillas/ con los nombres que documento_service espera.
"""
import re
import shutil
from pathlib import Path

from docx import Document
from docx.table import _Cell

NUEVAS = Path(__file__).parent          # este script vive en _nuevas/
BASE = NUEVAS.parent                    # backend/documentos/
SRC = BASE / "plantillas_sumoto"
DST = BASE / "plantillas"

MAP = {
    NUEVAS / "1. AUTORIZACION CONSULTA CIFIN - DATA.docx": "autorizacion_centrales.docx",
    SRC / "2. CARTA DE APROBACION SUMOTO.docx": "carta_aprobacion.docx",
    NUEVAS / "12. PAGARE SUMOTO.docx": "pagare.docx",
    SRC / "4. CARTA DE INSTRUCCIONES SUMOTO.docx": "carta_instrucciones.docx",
    SRC / "13. PRENDA ABIERTA SIN TENENCIA DEL ACREEDOR SOBRE VEHICULO.docx": "prenda.docx",
    NUEVAS / "9. POLITICAS DE CARTERA 2025.docx": "compromiso_cartera.docx",
}

RX_MARKER = re.compile(r"«[^»]+»")


def _parrafos(doc):
    """Todos los párrafos del cuerpo, tablas y celdas anidadas."""
    yield from doc.paragraphs
    for t in doc.tables:
        yield from _parrafos_tabla(t)


def _parrafos_tabla(tabla):
    for row in tabla.rows:
        for cell in row.cells:
            yield from cell.paragraphs
            for t in cell.tables:
                yield from _parrafos_tabla(t)


def normalizar_marcadores(doc):
    """Une en un solo run cada «CAMPO» partido en varios runs."""
    n = 0
    for p in _parrafos(doc):
        texto = "".join(r.text for r in p.runs)
        if "«" not in texto:
            continue
        pos = 0
        runs = list(p.runs)
        # reconstruye la posición acumulada por run
        spans = []  # (run_idx, start_in_run, end_in_run)
        cursor = 0
        bounds = []
        for i, r in enumerate(runs):
            bounds.append((i, cursor, cursor + len(r.text)))
            cursor += len(r.text)
        for m in RX_MARKER.finditer(texto):
            a, b = m.span()
            cubiertos = [x for x in bounds if x[1] < b and x[2] > a]
            if len(cubiertos) <= 1:
                continue
            i0, s0, e0 = cubiertos[0]
            iN, sN, eN = cubiertos[-1]
            marca = texto[a:b]
            r0 = runs[i0]
            pref = r0.text[: a - s0]
            r0.text = pref + marca
            for i, s, e in cubiertos[1:-1]:
                runs[i].text = ""
            rN = runs[iN]
            rN.text = rN.text[b - sN:]
            n += 1
            # recalcular tras mutar
            texto = "".join(r.text for r in p.runs)
            runs = list(p.runs)
            cursor = 0
            bounds = []
            for i, r in enumerate(runs):
                bounds.append((i, cursor, cursor + len(r.text)))
                cursor += len(r.text)
    return n


def _reemplaza_blancos(p, sustituciones):
    """Sustituye secuencias de guiones bajos por marcadores, en orden.
    ``None`` conserva el blanco original."""
    texto = "".join(r.text for r in p.runs)
    if "_" not in texto:
        return 0
    it = iter(sustituciones)

    def _cada(m):
        try:
            s = next(it)
        except StopIteration:
            return m.group()
        return m.group() if s is None else s

    nuevo = re.sub(r"_{3,}", _cada, texto)
    if nuevo == texto:
        return 0
    # preserva el formato del primer run con texto
    for r in p.runs:
        r.text = ""
    p.runs[0].text = nuevo
    return 1


def inyectar_prenda(doc):
    campos = {"MODELO": "«MODELO»", "MARCA": "«MARCA»",
              "LÍNEA": "«LINEA»", "COLOR": "«COLOR»"}
    n = 0
    for t in doc.tables:
        for row in t.rows:
            if len(row.cells) >= 2:
                label = row.cells[0].text.strip().upper().rstrip(".")
                valor = row.cells[1]
                if label in campos and not valor.text.strip():
                    valor.paragraphs[0].add_run(campos[label])
                    n += 1
    return n


def inyectar_pagare(doc):
    n = 0
    for p in _parrafos(doc):
        if "%" in p.text and "_" in p.text:
            for r in p.runs:
                if "_" in r.text:
                    r.text = r.text.replace("_", "")
                    r.text = r.text.replace("(%)", "(«TASA»%)")
                    r.text = r.text.replace("(%)", "(«TASA»%)")
                    r.text = r.text.replace("()", "(«TASA»)")
                    r.text = re.sub(r"\(\s*%\)", "(«TASA»%)", r.text)
                    r.text = re.sub(r"\(\s*\)", "(«TASA»)", r.text)
                    n += 1
        if "«TIPO ID»" in p.text or "«NÚMERO»" in p.text:
            for r in p.runs:
                r.text = r.text.replace("«TIPO ID»", "«TIPO_ID»")
                r.text = r.text.replace("«NÚMERO»", "«CÉDULA»")
    return n


def inyectar_politicas(doc):
    n = 0
    for p in _parrafos(doc):
        t = p.text
        if "Yo " in t and "mayor de edad" in t and "_" in t:
            n += _reemplaza_blancos(
                p, ["«NOMBRE_COMPLETO»", "«CÉDULA»", "«CIUDAD_CC»"]
            )
        elif re.match(r"^\s*Nombre:\s*_+", t):
            n += _reemplaza_blancos(p, ["«NOMBRE_COMPLETO»"])
        elif re.match(r"^\s*Cédula:\s*_+", t):
            n += _reemplaza_blancos(p, ["«CÉDULA»"])
        elif re.match(r"(?i)^\s*Correo electrónico autorizado:\s*_+", t):
            n += _reemplaza_blancos(p, ["«CORREO»"])
        elif re.match(r"(?i)^\s*Teléfono Celular autorizado:\s*_+", t):
            n += _reemplaza_blancos(p, ["«TELEFONO»"])
        elif "VENCIMIENTO DE CADA CUOTA" in t.upper() and "_" in t:
            n += _reemplaza_blancos(p, ["«DIA_PAGO»"])
        elif "Acepto tratamiento de datos personales" in t:
            # La firma OTP es consentimiento informado: se marca SI.
            n += _reemplaza_blancos(p, ["X", None])
        elif "CUOTA MENSUAL" in t and "_" in t:
            n += _reemplaza_blancos(p, ["«CUOTA»", "«PLAZO»"])
        elif "FECHA INICIO" in t.upper() and "_" in t:
            n += _reemplaza_blancos(p, ["«FECHA_INICIO»", "«FECHA_FIN»"])
    return n


def main():
    resumen = {}
    for src, nombre in MAP.items():
        tmp = NUEVAS / ("_tmp_" + nombre)
        shutil.copyfile(src, tmp)
        doc = Document(str(tmp))
        fus = normalizar_marcadores(doc)
        inj = 0
        if nombre == "prenda.docx":
            inj = inyectar_prenda(doc)
        elif nombre == "pagare.docx":
            inj = inyectar_pagare(doc)
        elif nombre == "compromiso_cartera.docx":
            inj = inyectar_politicas(doc)
        doc.save(str(DST / nombre))
        resumen[nombre] = (fus, inj)
    for k, (f, i) in resumen.items():
        print(f"{k}: {f} marcadores fusionados, {i} inyectados")


if __name__ == "__main__":
    main()
