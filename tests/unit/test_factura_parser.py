"""Parser de facturas de vehículo: formatos soportados y helpers."""

import io
from decimal import Decimal

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from backend.integrations.factura.factura_parser import (
    _numero,
    extraer_texto_pdf,
    extraer_y_parsear,
    nombres_coinciden,
    solo_digitos,
)


def _pdf_con_texto(lineas: list[str]) -> bytes:
    """PDF mínimo de una página con texto extraíble (sin reportlab)."""
    ops = ["BT /F1 10 Tf"]
    for i, linea in enumerate(lineas):
        esc = (
            linea.replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )
        ops.append(f"1 0 0 1 40 {760 - i * 14} Tm ({esc}) Tj")
    ops.append("ET")
    writer = PdfWriter()
    pagina = writer.add_blank_page(width=612, height=792)
    contenido = DecodedStreamObject()
    contenido.set_data("\n".join(ops).encode("latin-1"))
    pagina[NameObject("/Contents")] = contenido
    pagina[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {
                    NameObject("/F1"): DictionaryObject(
                        {
                            NameObject("/Type"): NameObject("/Font"),
                            NameObject("/Subtype"): NameObject("/Type1"),
                            NameObject("/BaseFont"): NameObject("/Helvetica"),
                        }
                    )
                }
            )
        }
    )
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# Layout real de la factura electrónica SUMOTO (texto extraído).
TEXTO_SUMOTO = [
    "PALACIOS ORBES MILTON ALBERTO",
    "Cédula de ciudadanía  14704104",
    "CL 40 9 15",
    "Palmira",
    "PEREA GUERRERO YURANI",
    "MTEC 2434",
    "2027 124",
    "9F2C91252V5009278 AKT GRIS MATE",
    "ZS154FMI-",
    "38V102908",
    "5,453,781.51 AK125FLEX-2027 5,117,647.06",
    "RESOLUCION DIAN No. 18764099982895 DEL 10 DE 10 DE 2025 AUTORIZA "
    "DEL MTEC 1663 AL MTEC 10000",
    "5,453,781.51",
    "972,352.94",
    "0.00",
    "6,090,000.00",
    "0.00",
    "336,134.45",
]


def test_parser_sumoto_extrae_todos_los_campos():
    d = extraer_y_parsear(_pdf_con_texto(TEXTO_SUMOTO), "application/pdf")
    assert d is not None
    assert d.formato == "sumoto"
    assert d.numero_factura == "MTEC-2434"
    assert d.nit_comprador == "14704104"
    assert d.nombre_comprador == "PALACIOS ORBES MILTON ALBERTO"
    assert d.marca == "AKT"
    assert d.referencia == "AK125FLEX-2027"
    assert d.anio == "2027"
    assert d.color == "GRIS MATE"
    # El motor llega partido en dos líneas y se une.
    assert d.numero_motor == "ZS154FMI-38V102908"
    assert d.vin == "9F2C91252V5009278"
    assert d.numero_chasis == "9F2C91252V5009278"
    assert d.cilindraje == "124"
    assert d.total == Decimal("6090000.00")


def test_parser_rechaza_formato_desconocido():
    pdf = _pdf_con_texto(["Hola mundo", "esto no es una factura"])
    assert extraer_y_parsear(pdf, "application/pdf") is None


def test_parser_rechaza_mime_no_pdf():
    assert extraer_y_parsear(b"\x89PNG\r\n\x1a\n", "image/png") is None


def test_pdf_danado_devuelve_none():
    assert extraer_texto_pdf(b"no es un pdf") is None


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("4.865.000,00", Decimal("4865000.00")),  # es-CO
        ("5,453,781.51", Decimal("5453781.51")),  # en-US
        ("6,090,000.00", Decimal("6090000.00")),  # en-US con ,00
        ("6090000", Decimal("6090000")),
        ("972,35", Decimal("972.35")),  # coma decimal corta
        ("1.234.567", Decimal("1234567")),  # puntos de miles
    ],
)
def test_numero_ambos_formatos(texto, esperado):
    assert _numero(texto) == esperado


def test_solo_digitos():
    assert solo_digitos("800235505-9") == "8002355059"
    assert solo_digitos(None) == ""
    assert solo_digitos(" 1.234.567 ") == "1234567"


@pytest.mark.parametrize(
    "factura,cliente,esperado",
    [
        ("PALACIOS ORBES MILTON ALBERTO", "Milton Alberto Palacios Orbes", True),
        # La factura puede traer menos apellidos: subset en cualquier dirección.
        ("MOÑA LEIDY", "LEIDY VIVIANA MOÑA GRUESO", True),
        ("PEREZ JUAN", "GARCIA MARIA", False),
        (None, "ALGUIEN", None),
        ("ALGUIEN", None, None),
    ],
)
def test_nombres_coinciden(factura, cliente, esperado):
    assert nombres_coinciden(factura, cliente) is esperado
