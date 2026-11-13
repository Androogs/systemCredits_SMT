# -*- coding: utf-8 -*-
"""Prepara los documentos 3, 5, 6 y 11 del paquete Sumoto como
plantillas activas: inyecta marcadores «CAMPO» en los blancos y los
copia a plantillas/ con los nombres que documento_service espera.

Doc 8 (Formularios RUNT) y 10 (Solicitud Sumoto escaneada) no llevan
marcadores: el primero se diligencia en el organismo de tránsito y el
segundo es una imagen escaneada — no son llenables por firma OTP.
"""
import re
import shutil
from pathlib import Path

from docx import Document

NUEVAS = Path(__file__).parent          # este script vive en _nuevas/
BASE = NUEVAS.parent                    # backend/documentos/
SRC = BASE / "plantillas_sumoto"
DST = BASE / "plantillas"

MAP = {
    NUEVAS / "3. AUTORIZACION TRATAMIENTO DE DATOS PERSONALES.docx": "autorizacion_datos.docx",
    NUEVAS / "5. CONTRATO DE COMPRA VENTA EN BLANCO.docx": "compra_venta.docx",
    NUEVAS / "6. DACION EN PAGO DPTO CREDITO.docx": "dacion_pago.docx",
    SRC / "11. TRANSFERENCIA DE DOMINIO.docx": "transferencia_dominio.docx",
}

RX_BLANCO = re.compile(r"_{3,}")
RX_TAB = re.compile(r"\t+")


def _parrafos(doc):
    yield from doc.paragraphs
    for t in doc.tables:
        yield from _parrafos_tabla(t)


def _parrafos_tabla(tabla):
    for row in tabla.rows:
        for cell in row.cells:
            yield from cell.paragraphs
            for t in cell.tables:
                yield from _parrafos_tabla(t)


def _reescribir(p, nuevo_texto):
    """Escribe texto en el primer run y vacía los demás (mismo
    mecanismo que swap.py: conserva formato del párrafo)."""
    if not p.runs:
        p.add_run(nuevo_texto)
        return
    for r in p.runs:
        r.text = ""
    p.runs[0].text = nuevo_texto


def _reescribir_segmentos(p, segmentos):
    """Escribe segmentos (texto, negrita) como runs separados — para
    poner el dato en negrita sin tocar la etiqueta."""
    for r in p.runs:
        r.text = ""
    primero = True
    for texto, negrita in segmentos:
        if primero and p.runs:
            run = p.runs[0]
            run.text = texto
            primero = False
        else:
            run = p.add_run(texto)
        if negrita:
            run.bold = True


def _reemplaza_blancos(p, sustituciones):
    """Sustituye secuencias de guiones en orden; None = conservar."""
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

    nuevo = RX_BLANCO.sub(_cada, texto)
    if nuevo == texto:
        return 0
    _reescribir(p, nuevo)
    return 1


def _reemplaza_tabs(p, sustituciones):
    """Sustituye corridas de tabulaciones (blancos de formulario) en
    orden; cada marcador conserva un tab para no romper las columnas."""
    texto = "".join(r.text for r in p.runs)
    if "\t" not in texto:
        return 0
    it = iter(sustituciones)

    def _cada(m):
        try:
            s = next(it)
        except StopIteration:
            return m.group()
        return m.group() if s is None else s

    nuevo = RX_TAB.sub(_cada, texto)
    if nuevo == texto:
        return 0
    _reescribir(p, nuevo)
    return 1


def _swap_anio(p):
    """'de 20____.' → 'de «AÑO».'"""
    texto = "".join(r.text for r in p.runs)
    nuevo = re.sub(r"20_{2,}", "«AÑO»", texto)
    if nuevo != texto:
        _reescribir(p, nuevo)
        return 1
    return 0


# ------------------------------------------------------------------
def inyectar_autorizacion_datos(doc):
    """Doc 3: ciudad/fecha de firma, nombre e identificación."""
    n = 0
    for p in _parrafos(doc):
        t = p.text
        if t.strip().startswith("Se firma en"):
            n += _reemplaza_blancos(
                p, ["«CIUDAD_FIRMA»", "«DIA»", "«MES»"]
            )
            n += _swap_anio(p)
        elif re.match(r"^\s*Nombre:\s*_+", t):
            # 'Nombre ___ Huella ___': solo el primer blanco
            n += _reemplaza_blancos(p, ["«NOMBRE_COMPLETO»", None])
        elif re.match(r"^\s*Identificación:\s*_+", t):
            n += _reemplaza_blancos(p, ["«CÉDULA»"])
    return n


def inyectar_compra_venta(doc):
    """Doc 5: comprador (el vendedor queda en blanco — es contrato en
    blanco), vehículo, precio y fecha de firma."""
    n = 0
    for p in _parrafos(doc):
        t = p.text
        if "quien en adelante se denominará EL VENDEDOR" in t:
            # 9 blancos: vendedor = el asesor que radicó la solicitud
            # (nombre y cédula); su ciudad y paréntesis quedan en
            # blanco. 5 del comprador.
            n += _reemplaza_blancos(
                p,
                [
                    "«ASESOR_NOMBRE»", "«ASESOR_CEDULA»", None, None,
                    "«NOMBRE_COMPLETO»", "«CÉDULA»", "«CIUDAD_CC»",
                    "«CIUDAD_RESIDENCIA»", "«TELEFONO»",
                ],
            )
        elif re.match(r"^\s*Marca\s+_", t):
            n += _reemplaza_blancos(p, ["«MARCA»", "«MODELO»"])
        elif re.match(r"^\s*Tipo\s*Particular", t) or re.match(
            r"^\s*Color\s+_", t
        ):
            n += _reemplaza_blancos(p, ["«COLOR»"])
        elif re.match(r"^\s*Línea\s+_", t):
            # Línea, Placas (moto nueva sin placa), Tránsito (ciudad firma)
            n += _reemplaza_blancos(p, ["«LINEA»", None, "«CIUDAD_FIRMA»"])
        elif re.match(r"^\s*No motor\s+_", t):
            n += _reemplaza_blancos(p, ["«MOTOR»", "«CHASIS»"])
        elif "PESOS M/CTE" in t and "_" in t:
            n += _reemplaza_blancos(
                p, ["«PRECIO_MOTO_LETRAS»", "«PRECIO_MOTO»"]
            )
        elif "secretaria de tránsito de" in t:
            n += _reemplaza_blancos(p, ["«CIUDAD_FIRMA»", None])
        elif "se firman tres" in t:
            n += _reemplaza_blancos(p, ["«DIA»", "«MES»"])
            n += _swap_anio(p)
        elif re.match(r"^\s*VENDEDOR\s*\t", t) and "COMPRADOR" in t:
            # Rótulo del bloque de firmas: nombre del asesor que
            # radicó bajo 'VENDEDOR'.
            _reescribir(p, t.replace("VENDEDOR", "VENDEDOR «ASESOR_NOMBRE»", 1))
            n += 1
        elif re.match(r"^\s*CC\._+", t):
            # CC vendedor = asesor que radicó; su 'de' queda en
            # blanco. CC comprador = cliente.
            n += _reemplaza_blancos(
                p, ["«ASESOR_CEDULA»", None, "«CÉDULA»", "«CIUDAD_CC»"]
            )
    return n


def inyectar_dacion(doc):
    """Doc 6: tabla del vehículo, deudor y cédula; montos y avalúo en
    blanco (se liquidan cuando se ejecuta la dación)."""
    n = 0
    celda_marcas = {
        "MARCA:": "«MARCA»",
        "LINEA :": "«LINEA»",
        "COLOR :": "«COLOR»",
        "MODELO:": "«MODELO»",
        "MOTOR No.": "«MOTOR»",
        "CHASIS No.": "«CHASIS»",
        "CLASE DE VEHÍCULO:": "MOTOCICLETA",
    }
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                label = cell.text.strip()
                if label in celda_marcas:
                    cell.paragraphs[0].add_run(" " + celda_marcas[label])
                    n += 1
    for p in _parrafos(doc):
        t = p.text
        if t.strip().startswith("C.C. #"):
            # C.C. del deudor (izquierda); la derecha es SUMOTO S.A.
            tabs = t.split("\t")
            tabs[0] = tabs[0].rstrip() + " «CÉDULA»"
            _reescribir(p, "\t".join(tabs))
            n += 1
        elif re.match(r"^\s*Palmira,\s*_+", t):
            n += _reemplaza_blancos(p, ["«FECHA_FIRMA»"])
        elif "a nombre de el DEUDOR" in t and "_" in t:
            n += _reemplaza_blancos(p, ["«NOMBRE_COMPLETO»"])
        elif re.match(r"^\s*NOMBRE\s+_+", t):
            n += _reemplaza_blancos(p, ["«NOMBRE_COMPLETO»"])
        elif re.match(r"^\s*CEDULA\s+_+", t):
            n += _reemplaza_blancos(p, ["«CÉDULA»"])
    return n


def inyectar_transferencia(doc):
    """Doc 11: ciudad/fecha, declarante, vehículo, lugar y firma.
    Los blancos del original son tabulaciones, no guiones."""
    n = 0
    for p in _parrafos(doc):
        t = p.text
        if t.strip().startswith("Ciudad") and "Fecha" in t:
            nuevo = t.replace("Ciudad", "Ciudad «CIUDAD_FIRMA»", 1)
            nuevo = nuevo.replace("Fecha:", "Fecha: «FECHA_FIRMA»", 1)
            _reescribir(p, nuevo)
            n += 1
        elif "residente en la ciudad de" in t and "\t" in t:
            # 4 blancos tabulados: nombre, ciudad, dirección, cédula.
            # El tab que reemplaza el marcador era el separador: sin él
            # las comas quedan separadas y las etiquetas pegadas al valor.
            n += _reemplaza_tabs(
                p,
                [
                    "«NOMBRE_COMPLETO»",
                    "«CIUDAD_RESIDENCIA»",
                    " «DIRECCION»",
                    " «CÉDULA»",
                ],
            )
        elif re.match(r"^\s*MARCA\s*\t", t):
            _reescribir_segmentos(p, [
                ("MARCA: ", False), ("«MARCA»", True), (" \t", False),
                ("MODELO: ", False), ("«MODELO»", True), ("\t", False),
            ])
            n += 1
        elif re.match(r"^\s*CLASE\s*\t", t) or t.strip() == "CLASE COLOR":
            _reescribir_segmentos(p, [
                ("CLASE: ", False), ("MOTOCICLETA", True), (" \t", False),
                ("COLOR: ", False), ("«COLOR»", True), ("\t", False),
            ])
            n += 1
        elif "NO. MOTOR" in t:
            _reescribir_segmentos(p, [
                ("NO. MOTOR: ", False), ("«MOTOR»", True), ("\t", False),
                ("CHASIS: ", False), ("«CHASIS»", True), (" \t", False),
            ])
            n += 1
        elif "se firma en la ciudad de" in t:
            n += _reemplaza_tabs(
                p,
                ["«CIUDAD_FIRMA»", " «DIA» ", "«MES»", "«AÑO»"],
            )
        elif t.strip().startswith("NOMBRE/APELLIDO"):
            _reescribir(p, t + " «NOMBRE_COMPLETO»")
            n += 1
        elif t.strip() == "C.C.":
            _reescribir(p, t + " «CÉDULA»")
            n += 1
    return n


def main():
    inyectores = {
        "autorizacion_datos.docx": inyectar_autorizacion_datos,
        "compra_venta.docx": inyectar_compra_venta,
        "dacion_pago.docx": inyectar_dacion,
        "transferencia_dominio.docx": inyectar_transferencia,
    }
    for src, nombre in MAP.items():
        tmp = NUEVAS / ("_tmp_" + nombre)
        shutil.copyfile(src, tmp)
        doc = Document(str(tmp))
        n = inyectores[nombre](doc)
        doc.save(str(DST / nombre))
        print(f"{nombre}: {n} inserciones")


if __name__ == "__main__":
    main()
