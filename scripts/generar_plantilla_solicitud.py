"""Transforma 'Informes Pacifico/Plantillas/7. solicitudCredito.docx' en
'backend/documentos/plantillas/solicitud_credito.docx': reemplaza los
datos de muestra (solicitud 735) por tokens {{CAMPO}} que
DocumentoService sustituye como texto literal (igual que
compromiso_cartera.docx).

Se ejecuta una sola vez por cambio de plantilla:

    .venv/Scripts/python.exe scripts/generar_plantilla_solicitud.py

Cada párrafo se reconstruye con dos formatos: '**etiqueta**' se escribe
en negrita (como el original) y '{{TOKEN}}'/texto plano en formato
normal. El script aborta si alguna etiqueta de muestra no coincide — la
plantilla queda verificada contra la estructura esperada.
"""

import sys
from pathlib import Path

from docx import Document

ORIGEN = Path(
    "backend/documentos/plantillas_sumoto/7. solicitudCredito735.docx"
)
DESTINO = Path("backend/documentos/plantillas/solicitud_credito.docx")

# Huellas SHA-256 de los artefactos de la firma electrónica de la
# solicitud de muestra 735: el QR de verificación y la rúbrica del
# titular. Ninguno puede quedar en la plantilla generada.
HUELLAS_FIRMA_MUESTRA = {
    "05fb103c9a6f76995cd41d4506e6a4ab28423f39caf9af3b0a336e7e7ee3760f":
        "QR de verificación",
    "ca61fbbb9807d07c6c81116f7d0cd0443b83e011b68e1bdf54b8cc94892b8eeb":
        "rúbrica del titular",
}
# Imágenes que sí se conservan: logo de Inversiones Pacífico y la
# cláusula legal de la firma electrónica (imagen de texto legal).
HUELLAS_CONSERVAR = {
    "effb59786809aa24ebd2d9f68d4911ad733ae509f78a99a1e0856ab5ed63fcd3",
    "f2627590be7e5dd7b888144089cbd1bff3e9616f94bf5958fb6273acb6e97ba0",
    # logo SUMOTO S.A. (variante de la solicitud 735 re-guardada)
    "e84defc8e621ce02c44df20548314a2630d15914866d63763ca7d56b8ac969a3",
}

# Párrafos sueltos del cuerpo (fuera de la tabla).
PARRAFOS = {
    "FECHA:": "**FECHA:** {{FECHA_SOLICITUD}} **No. SOLICITUD:** {{NUM_SOLICITUD}}",
    "Se firma en": (
        "Se firma en {{CIUDAD_FIRMA}} el {{DIA}} de {{MES}} del año {{AÑO}}"
    ),
}

# Celdas de la tabla: (fila, columna) -> lista de párrafos nuevos, en
# orden. Cada entrada reemplaza el párrafo no vacío i-ésimo de la celda.
CELDAS = {
    # INFORMACIÓN DEL TITULAR
    (1, 0): [
        "**NOMBRE COMPLETO:** {{NOMBRE_COMPLETO}} **TIPO DE DOCUMENTO:** "
        "{{TIPO_DOCUMENTO}} **FECHA EXPEDICIÓN:** {{FECHA_EXPEDICION}}",
        "**FECHA DE NACIMIENTO:** {{FECHA_NACIMIENTO}}",
        "**DEPARTAMENTO NACIMIENTO:** {{DEPARTAMENTO_NACIMIENTO}}",
    ],
    (1, 1): [
        "**NUMERO DE DOCUMENTO:** {{NUMERO_DOCUMENTO}}",
        "**CIUDAD DE EXPEDICIÓN:** {{CIUDAD_EXPEDICION}}",
        "**CIUDAD DE NACIMIENTO:** {{CIUDAD_NACIMIENTO}}",
        "**PAÍS DE NACIMIENTO:** {{PAIS_NACIMIENTO}}",
    ],
    # CONTACTO
    (3, 0): ["**CELULAR:** {{CELULAR}}"],
    (3, 1): ["**EMAIL:** {{EMAIL}}"],
    # RESIDENCIA
    (5, 0): [
        "**DIRECCIÓN:** {{DIRECCION}} **CIUDAD/MUNICIPIO:** "
        "{{CIUDAD_MUNICIPIO}} **ESTRATO:** {{ESTRATO}}"
    ],
    (5, 1): [
        "**BARRIO:** {{BARRIO}}",
        "**TIPO DE VIVIENDA:** {{TIPO_VIVIENDA}}",
        "**ZONA RURAL:** {{ZONA_RURAL}}",
    ],
    # PERSONAL
    (7, 0): [
        "**ESTADO CIVIL:** {{ESTADO_CIVIL}}",
        "**NÚMERO DE HIJOS:** {{NUM_HIJOS}}",
    ],
    (7, 1): [
        "**PERSONAS A CARGO:** {{PERSONAS_A_CARGO}}",
        "**¿ES CABEZA DE FAMILIA?:** {{CABEZA_FAMILIA}}",
    ],
    # FINANCIERA
    (9, 0): [
        "**¿CUENTA CON BIENES RAÍCES?:** {{BIENES_RAICES}}",
        "**¿MOTO?:** {{MOTO}}",
        "**¿PRIMERA MOTO?:** {{PRIMERA_MOTO}}",
    ],
    (9, 1): [
        "**¿CUANTA CON VEHÍCULO?:** {{CUENTA_VEHICULO}}",
        "**¿CARRO?:** {{CARRO}}",
        "**¿ESTOY FINANCIANDO?:** {{ESTOY_FINANCIANDO}}",
    ],
    # LABORAL
    (11, 0): ["**PERFIL DEL CLIENTE:** {{PERFIL_CLIENTE}}"],
    (11, 1): ["**TIPO DE CONTRATO:** {{TIPO_CONTRATO}}"],
    (12, 0): ["**FECHA DE INGRESO:** {{FECHA_INGRESO}}"],
    (12, 1): ["**ANTIGÜEDAD LABORAL EN MESES:** {{ANTIGUEDAD_MESES}}"],
    (13, 0): ["**INGRESOS MENSUAL:** $ {{INGRESOS_MENSUAL}}"],
    (13, 1): ["**AÑOS CÁMARA DE COMERCIO:** {{ANIOS_CAMARA}}"],
    (14, 0): ["**NOMBRE DE LA EMPRESA:** {{NOMBRE_EMPRESA}}"],
    (14, 1): ["**CIUDAD DE LA EMPRESA:** {{CIUDAD_EMPRESA}}"],
    (15, 0): ["**ACTIVIDAD COMERCIAL:** {{ACTIVIDAD_COMERCIAL}}"],
    (15, 1): ["**CARGO:** {{CARGO}}"],
    (16, 0): ["**NIVEL EDUCATIVO:** {{NIVEL_EDUCATIVO}}"],
    (16, 1): ["**PROFESIÓN:** {{PROFESION}}"],
    # CRÉDITO — cada etiqueta es un párrafo aparte en la celda.
    (18, 0): [
        "**MARCA:** {{MARCA}}",
        "**MODELO (AÑO):** {{MODELO}}",
        "**TASA:** {{TASA}}",
    ],
    (18, 1): [
        "**REFERENCIA:** {{REFERENCIA}}",
        "**COLOR:** {{COLOR}}",
        "**PLAZO:** {{PLAZO}}",
    ],
    # HOJA DE NEGOCIO — (fila, 1) es la columna %, (fila, 2) el valor.
    (20, 2): ["$ {{VALOR_MOTO_IVA}}"],
    (21, 2): ["$ {{VALOR_MOTO_SIN_IVA}}"],
    (22, 1): ["{{DESCUENTO_PCT}}%"],
    (22, 2): ["$ {{DESCUENTO_VALOR}}"],
    (23, 2): ["$ {{SUBTOTAL_MOTO}}"],
    (24, 2): ["$ {{IVA_MOTO}}"],
    (25, 2): ["$ {{TOTAL_MOTO}}"],
    (26, 2): ["$ {{MATRICULA}}"],
    (27, 2): ["$ {{SOAT}}"],
    (28, 2): ["$ {{IMPUESTOS}}"],
    (29, 2): ["$ {{ACCESORIOS}}"],
    (30, 2): ["$ {{TOTAL_ADICIONALES}}"],
    (31, 1): ["{{CUOTA_INICIAL_PCT}}%"],
    (31, 2): ["$ {{CUOTA_INICIAL}}"],
    (32, 2): ["$ {{TOTAL_GENERAL}}"],
    (33, 1): ["{{FONDO_GARANTIA_PCT}}%"],
    (33, 2): ["$ {{FONDO_GARANTIA}}"],
    (34, 1): ["19%"],
    (34, 2): ["$ {{IVA_FONDO}}"],
    (35, 2): ["$ {{GASTOS_ADMINISTRATIVOS}}"],
    (36, 2): ["$ {{SALDO_A_FINANCIAR}}"],
    (37, 1): ["{{TASA}}%"],
    (37, 2): ["$ {{VALOR_FINANCIACION}}"],
    (38, 1): ["{{SEGURO_VIDA_PCT}}%"],
    (38, 2): ["$ {{VALOR_SEGURO_VIDA}}"],
    (39, 2): ["$ {{TOTAL_A_PAGAR}}"],
    (40, 2): ["$ {{CUOTA_FINANCIACION}}"],
    (41, 2): ["$ {{CUOTA_SEGURO_VIDA}}"],
    (42, 2): ["$ {{CUOTA_TOTAL}}"],
}


def _reconstruir(paragraph, spec: str) -> None:
    """Reescribe el párrafo alternando negrita por los '**' del spec:
    '**A:** {{X}} **B:** {{Y}}' -> runs ['A:'(bold), ' {{X}} '(normal), ...].

    Conserva el tamaño de fuente del párrafo original (8pt en la
    plantilla)."""
    runs = paragraph.runs
    if not runs:
        raise ValueError(f"párrafo sin runs: {paragraph.text!r}")
    size = next((r.font.size for r in runs if r.font.size is not None), None)
    for r in list(runs):
        r._r.getparent().remove(r._r)
    # Valores que venían como hipervínculo (email de muestra): el run del
    # enlace no sale en paragraph.runs, hay que quitar el w:hyperlink.
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    for link in paragraph._p.findall(f"{ns}hyperlink"):
        paragraph._p.remove(link)
    negrita = spec.startswith("**")
    for i, parte in enumerate(p for p in spec.split("**") if p):
        run = paragraph.add_run(parte)
        run.bold = negrita if i % 2 == 0 else not negrita
        if size is not None:
            run.font.size = size


def _limpiar_firma_muestra(doc) -> None:
    """Quita del paquete lo que venía de la firma electrónica de muestra.

    - El QR de verificación de la firma de la solicitud 735 y la rúbrica
      del titular de muestra: se identifican por la huella SHA-256 de su
      blob (la muestra es un documento fijo). Si la plantilla de origen
      cambia, las huellas ya no coinciden y el script aborta — hay que
      revisar la nueva firma y actualizar HUELLAS_FIRMA_MUESTRA.
    """
    import hashlib

    ns_r = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    ns_a = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    ns_pic = "{http://schemas.openxmlformats.org/drawingml/2006/picture}"
    ns_v = "{urn:schemas-microsoft-com:vml}"

    rids_qr = set()
    for rid, rel in doc.part.rels.items():
        if "image" not in rel.reltype:
            continue
        huella = hashlib.sha256(rel.target_part.blob).hexdigest()
        if huella in HUELLAS_FIRMA_MUESTRA:
            rids_qr.add(rid)
            print(f"{HUELLAS_FIRMA_MUESTRA[huella]} de muestra "
                  f"({rel.target_part.partname}); se elimina")
        elif huella not in HUELLAS_CONSERVAR:
            raise ValueError(
                f"imagen desconocida en la plantilla de origen "
                f"({rel.target_part.partname}, sha256 {huella}); revisa "
                "si es un artefacto de firma y actualiza las huellas"
            )

    body = doc.element.body
    # pic:pic y v:shape que dibujan el QR.
    for pic in body.iter(f"{ns_pic}pic"):
        if any(b.get(f"{ns_r}embed") in rids_qr for b in pic.iter(f"{ns_a}blip")):
            pic.getparent().remove(pic)
    for shape in body.iter(f"{ns_v}shape"):
        if any(
            i.get(f"{ns_r}id") in rids_qr
            for i in shape.iter(f"{ns_v}imagedata")
        ):
            shape.getparent().remove(shape)

    # Relaciones de imagen ya sin referencia en el documento (rúbrica).
    usados = {
        e.get(f"{ns_r}embed") or e.get(f"{ns_r}id")
        for e in body.iter()
        if e.get(f"{ns_r}embed") or e.get(f"{ns_r}id")
    }
    for rid in list(doc.part.rels):
        rel = doc.part.rels[rid]
        if "image" in rel.reltype and rid not in usados:
            print(f"media sin referencia eliminada: {rel.target_part.partname}")
            doc.part.drop_rel(rid)


def main() -> int:
    if not ORIGEN.exists():
        print(f"no existe {ORIGEN}")
        return 1
    doc = Document(str(ORIGEN))

    # Párrafos del cuerpo.
    for p in doc.paragraphs:
        texto = p.text.strip()
        for prefijo, spec in PARRAFOS.items():
            if texto.startswith(prefijo):
                _reconstruir(p, spec)
                print(f"párrafo: {texto[:40]!r} -> {spec[:50]!r}")
                break

    # Cuadros de texto (bloque de firma del deudor): vienen duplicados
    # por mc:AlternateContent; se reescriben todos con tokens.
    w_ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    from docx.text.paragraph import Paragraph

    for txbx in doc.element.body.iter(f"{w_ns}txbxContent"):
        for p_el in txbx.findall(f"{w_ns}p"):
            texto = "".join(t.text or "" for t in p_el.iter(f"{w_ns}t"))
            if "CEDULA DE CIUDADANIA" in texto:
                _reconstruir(
                    Paragraph(p_el, None),
                    "{{NOMBRE_COMPLETO}} {{TIPO_DOCUMENTO}} {{NUMERO_DOCUMENTO}}",
                )
                print(f"txbx firma: {texto[:60]!r} -> tokens")

    # Bloque de firma electrónica de la solicitud 735: el DOCX de muestra
    # trae el QR de verificación de ESA firma (UUID ajeno) y la rúbrica
    # del titular de muestra — ninguno puede quedar en la plantilla.
    _limpiar_firma_muestra(doc)

    tabla = doc.tables[0]
    aplicadas = 0
    for (fila, columna), specs in CELDAS.items():
        cell = tabla.rows[fila].cells[columna]
        vacios = [p for p in cell.paragraphs if p.text.strip()]
        if len(vacios) != len(specs):
            print(f"ERROR fila {fila} col {columna}: {len(vacios)} párrafos, "
                  f"esperaba {len(specs)} — ajusta CELDAS")
            return 1
        for p, spec in zip(vacios, specs):
            antes = p.text.strip()[:50]
            _reconstruir(p, spec)
            print(f"fila {fila}.{columna}: {antes!r} -> {spec[:60]!r}")
            aplicadas += 1
    print(f"{aplicadas} párrafos de celda reescritos")

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(DESTINO))
    print(f"-> {DESTINO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
