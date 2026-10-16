"""Parser y fusión del OCR de la cédula (amarilla y blanca), sin Tesseract.

Los textos reproducen la salida REAL de Tesseract observada con fotos de
celular (rótulos mal leídos, basura de la foto a la izquierda, ``C0L`` en el
MRZ…), pero con datos FICTICIOS: no se versionan cédulas reales.

Los espacios iniciales simulan la maquetación (posición horizontal).
"""

from datetime import date, timedelta

import pytest

from backend.services import ocr_service
from backend.services.ocr_parser import (
    CARA_FRONTAL,
    CARA_REVERSO,
    TIPO_AMARILLA,
    TIPO_BLANCA,
    Valor,
    Votacion,
    buscar_fecha,
    clasificar,
    lineas_desde_texto,
    parsear_mrz,
    parsear_texto,
)
from backend.services.ocr_service import (
    CampoOCR,
    LecturaCara,
    ResultadoOCR,
    comparar_con_esperados,
    fusionar_lecturas,
    leer_cedula,
    leer_mrz_reverso,
)

# --- Cédula blanca (digital): rótulo ENCIMA del valor -----------------------

BLANCA_ANVERSO = """\
cunapana  —  ww    REPUBLICA DE COLOMBIA
                   Apalidos             NUIP 1.234.567.890
  === >            PEREZ GOMEZ
  ? y              Nombres
  A E              ANA MARIA
                   Nacionalidad Estatura Sexo
  E                COL          1.62     F    He
                   Fethade nacimiento GS
  =" '             15MAR1995           O+
                   Lugar de nacimiento
                   CALI (VALLE)
                   Fecha y lugar de expedición
  ¿                20 ENE 2021, CALI
                   Fecha de expiración
                   15 MAYO 2035"""

# MRZ TD1 ficticio con dígitos de control válidos.
MRZ_L1 = "ICCOL012345678498765<<<<<<<<<<"
MRZ_L2 = "9503157F3503155COL1234567890<2"
MRZ_L3 = "PEREZ<GOMEZ<<ANA<MARIA<<<<<<<<"

# --- Cédula amarilla: rótulo DEBAJO del valor -------------------------------

AMARILLA_ANVERSO = """\
Kia UDLICA DE COLOMBIA
  IDENTIFICACIÓN PERSONAL
  CEDULA DE CIUDADANÍA
  Numero  80.123.456  |
  MARTINEZ LOPEZ  - |
  APELLIDOS   e. y
  CARLOS ANDRES  Ñ
  NOMBRES   X"""

AMARILLA_REVERSO = """\
LO      FECHA DE NACIMIENTO 05-JUN-1980
O       BOGOTA
CN      (CUNDINAMARCA)
EZ SS   LUGAR DE NACIMIENTO y
E       1.70     O+    M
E       ESTATURA G.S. RH SEXO.
oa      12-AGO-1998 BOGOTA
        FECHA Y LUGAR DE EXPEDICIÓN >
ÍNDICE DERECHO  REGISTRADOR NACIONAL
                FULANO DE TAL
P-0100100-00123456-M-0080123456-20200101 00123456A 1 8500000000"""


# --------------------------------------------------------------------------
# Clasificación
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "texto, esperado",
    [
        (BLANCA_ANVERSO, (TIPO_BLANCA, CARA_FRONTAL)),
        ("\n".join([MRZ_L1, MRZ_L2, MRZ_L3]), (TIPO_BLANCA, CARA_REVERSO)),
        (AMARILLA_ANVERSO, (TIPO_AMARILLA, CARA_FRONTAL)),
        (AMARILLA_REVERSO, (TIPO_AMARILLA, CARA_REVERSO)),
    ],
)
def test_clasifica_tipo_y_cara_por_contenido(texto, esperado):
    tipo, cara, _ = clasificar(lineas_desde_texto(texto))
    assert (tipo, cara) == esperado


def test_texto_sin_cedula_no_se_clasifica():
    assert clasificar(lineas_desde_texto("Ctrl Alt\nunitec U.S.A."))[:2] == (None, None)


# --------------------------------------------------------------------------
# Cédula blanca
# --------------------------------------------------------------------------


def test_blanca_anverso_extrae_todos_los_campos():
    r = parsear_texto(BLANCA_ANVERSO)
    campos = {k: v.valor for k, v in r.campos.items()}
    assert campos == {
        "numero_documento": "1234567890",
        "apellidos": "PEREZ GOMEZ",
        "nombres": "ANA MARIA",
        "sexo": "F",
        "fecha_nacimiento": "1995-03-15",
        "lugar_nacimiento": "CALI (VALLE)",
        "fecha_expedicion": "2021-01-20",
        "ciudad_expedicion": "CALI",
        "fecha_expiracion": "2035-05-15",
    }


def test_mrz_valida_digitos_de_control():
    mrz = parsear_mrz([MRZ_L1, MRZ_L2, MRZ_L3])
    assert mrz["numero_documento"] == "1234567890"
    assert mrz["apellidos"] == "PEREZ GOMEZ"
    assert mrz["nombres"] == "ANA MARIA"
    assert mrz["fecha_nacimiento"] == "1995-03-15"
    assert mrz["fecha_expiracion"] == "2035-03-15"
    assert mrz["sexo"] == "F"
    assert mrz["control_nacimiento"] and mrz["control_expiracion"] and mrz["control_compuesto"]


@pytest.mark.parametrize(
    "lineas",
    [
        # O↔0 en la nacionalidad y en el serial (lectura real de Tesseract).
        ["ICCOLO12345678498765<<<<<<<<<<", "9503157F3503155C0L1234567890<2", MRZ_L3],
        # Basura del borde pegada al inicio y al final de cada línea.
        ["==] 1CCOLO12345678498765<<<<< ==", "=1 9503157F3503155C0L1234567890<2 5 Z",
         "=== PEREZ<GOMEZ<<ANA<MARIA<<<<<<e"],
        # Relleno final truncado y 'I' leída como '1'.
        ["10C0L012345678498765<<<<", "9503157F3503155COL1234567890<2", "PEREZ<GOMEZ<<ANA<MARIA<<<"],
    ],
)
def test_mrz_tolera_errores_reales_de_ocr(lineas):
    mrz = parsear_mrz(lineas)
    assert mrz["numero_documento"] == "1234567890"
    assert mrz["nombres"] == "ANA MARIA"
    assert mrz["apellidos"] == "PEREZ GOMEZ"
    assert mrz["control_compuesto"] is True


def test_mrz_no_confunde_el_serial_de_la_tarjeta_con_la_cedula():
    """Regresión: el parser anterior tomaba la línea 1 y devolvía el serial."""
    mrz = parsear_mrz(["ICCOLO12345678498765<<<<<<<<<<", "9503157F3503155C0L1234567890<2"])
    assert mrz["numero_documento"] == "1234567890"


def test_mrz_con_digito_erroneo_no_valida():
    mrz = parsear_mrz([MRZ_L1, "9503167F3503155COL1234567890<2", MRZ_L3])
    assert mrz["control_nacimiento"] is False


def test_sin_mrz_devuelve_vacio():
    assert parsear_mrz("REPUBLICA DE COLOMBIA\nSIN CODIGO") == {}


# --------------------------------------------------------------------------
# Cédula amarilla
# --------------------------------------------------------------------------


def test_amarilla_anverso_valor_encima_del_rotulo():
    """Regresión: antes tomaba la línea SIGUIENTE al rótulo (nombres como apellidos)."""
    r = parsear_texto(AMARILLA_ANVERSO)
    assert r.campos["numero_documento"].valor == "80123456"
    assert r.campos["apellidos"].valor == "MARTINEZ LOPEZ"
    assert r.campos["nombres"].valor == "CARLOS ANDRES"


def test_amarilla_reverso_extrae_datos_y_linea_codigo():
    r = parsear_texto(AMARILLA_REVERSO)
    campos = {k: v.valor for k, v in r.campos.items()}
    assert campos["fecha_nacimiento"] == "1980-06-05"
    assert campos["lugar_nacimiento"] == "BOGOTA (CUNDINAMARCA)"
    assert campos["fecha_expedicion"] == "1998-08-12"
    assert campos["ciudad_expedicion"] == "BOGOTA"
    assert campos["sexo"] == "M"
    # Número de la línea del pie, sin ceros de relleno.
    assert campos["numero_documento"] == "80123456"
    assert r.campos["numero_documento"].fuente == "codigo_reverso"
    # El nombre del registrador nunca se toma como dato de la persona.
    assert "nombres" not in campos and "apellidos" not in campos


# --------------------------------------------------------------------------
# Fechas
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "texto, tipo, esperado",
    [
        ("24 ABR 2002", "nacimiento", "2002-04-24"),
        ("24ABR2002", "nacimiento", "2002-04-24"),
        ("09-NOV-2002", "nacimiento", "2002-11-09"),
        ("31 MAYO 2034", "expiracion", "2034-05-31"),
        ("10-N0V-2020 PALMIRA", "expedicion", "2020-11-10"),
        ("14MAR1091", "nacimiento", None),  # 1991 leído como 1091: se descarta
        ("01 ENE 2099", "nacimiento", None),  # nacimiento en el futuro
    ],
)
def test_fechas(texto, tipo, esperado):
    encontrada = buscar_fecha(texto, tipo)
    assert (encontrada[0] if encontrada else None) == esperado


# --------------------------------------------------------------------------
# Votación entre pasadas
# --------------------------------------------------------------------------


def test_votacion_elige_mayoria_y_conserva_espacios():
    v = Votacion()
    v.agregar({"nombres": Valor("ANA MARIA", 80)})
    v.agregar({"nombres": Valor("PATRKR ANA", 90)})
    v.agregar({"nombres": Valor("ANAMARIA", 85)})
    elegido, votos = v.mejor("nombres")
    assert elegido.valor == "ANA MARIA" and votos == 2
    assert v.estable(("nombres",))


# --------------------------------------------------------------------------
# Fusión anverso + reverso
# --------------------------------------------------------------------------


def _lectura(tipo, cara, **campos) -> dict:
    return LecturaCara(
        disponible=True,
        tipo_cedula=tipo,
        cara=cara,
        campos={k: CampoOCR(*v) for k, v in campos.items()},
    ).to_dict()


ANVERSO_BLANCA = _lectura(
    TIPO_BLANCA, CARA_FRONTAL,
    numero_documento=("1234567890", 90, "anverso"),
    nombres=("ANA MARÍA", 88, "anverso"),
    apellidos=("PEREZ GOMEZ", 90, "anverso"),
    fecha_nacimiento=("1995-03-16", 70, "anverso"),  # mal leída en el anverso
    lugar_nacimiento=("CALI (VALLE)", 90, "anverso"),
    fecha_expedicion=("2021-01-20", 90, "anverso"),
    ciudad_expedicion=("CALI", 90, "anverso"),
)
REVERSO_BLANCA = _lectura(
    TIPO_BLANCA, CARA_REVERSO,
    numero_documento=("1234567890", 99, "mrz"),
    nombres=("ANA MARIA", 92, "mrz"),
    apellidos=("PEREZ GOMEZ", 92, "mrz"),
    fecha_nacimiento=("1995-03-15", 99, "mrz"),
    sexo=("F", 95, "mrz"),
    fecha_expiracion=("2035-03-15", 99, "mrz"),
)


@pytest.mark.parametrize("orden", [("f", "r"), ("r", "f")])
def test_fusion_no_depende_del_orden_y_el_mrz_validado_manda(orden):
    lecturas = {}
    for lado in orden:
        if lado == "f":
            lecturas["cedula_frontal"] = ANVERSO_BLANCA
        else:
            lecturas["cedula_reverso"] = REVERSO_BLANCA
    r = fusionar_lecturas(lecturas)
    assert r.tipo_cedula == TIPO_BLANCA
    assert r.fecha_nacimiento.valor == "1995-03-15" and r.fecha_nacimiento.fuente == "mrz"
    # Mismo nombre en anverso y MRZ: se conserva el anverso (con tilde).
    assert r.nombres.valor == "ANA MARÍA"
    assert r.lugar_nacimiento.valor == "CALI (VALLE)"
    assert r.sexo.valor == "F"
    assert r.advertencias == []


def test_fusion_detecta_anverso_y_reverso_de_personas_distintas():
    reverso = _lectura(TIPO_BLANCA, CARA_REVERSO, numero_documento=("9876543210", 99, "mrz"))
    r = fusionar_lecturas({"cedula_frontal": ANVERSO_BLANCA, "cedula_reverso": reverso})
    assert any("anverso" in a and "reverso" in a for a in r.advertencias)
    assert r.to_dict()["coincide"] is False


def test_fusion_detecta_tipos_mezclados_sin_mezclar_campos():
    reverso = _lectura(
        TIPO_AMARILLA, CARA_REVERSO,
        fecha_expedicion=("1998-08-12", 95, "reverso"),
        numero_documento=("80123456", 90, "codigo_reverso"),
    )
    r = fusionar_lecturas({"cedula_frontal": ANVERSO_BLANCA, "cedula_reverso": reverso})
    assert any("cédulas distintas" in a for a in r.advertencias)
    assert r.fecha_expedicion.valor == "2021-01-20"  # no se toma de la otra cédula


def test_fusion_advierte_cedula_vencida():
    vencida = (date.today() - timedelta(days=1)).isoformat()
    reverso = _lectura(TIPO_BLANCA, CARA_REVERSO, fecha_expiracion=(vencida, 99, "mrz"))
    r = fusionar_lecturas({"cedula_reverso": reverso})
    assert any("vencida" in a for a in r.advertencias)


def test_fusion_observa_cara_cambiada_e_ilegible():
    r = fusionar_lecturas({
        "cedula_frontal": _lectura(TIPO_AMARILLA, CARA_REVERSO, sexo=("M", 90, "reverso")),
        "cedula_reverso": LecturaCara(disponible=True).to_dict(),
    })
    assert any("parece ser el reverso" in o for o in r.observaciones)
    assert any("No se reconoció" in o for o in r.observaciones)
    assert r.advertencias == []  # son notas de calidad, no diferencias


# --------------------------------------------------------------------------
# Comparación contra lo digitado por el asesor
# --------------------------------------------------------------------------


def _resultado(**campos) -> ResultadoOCR:
    r = ResultadoOCR(disponible=True)
    for k, v in campos.items():
        setattr(r, k, CampoOCR(v, 90))
    return r


def test_sin_diferencias_no_hay_advertencias():
    r = comparar_con_esperados(
        _resultado(numero_documento="1234567890", nombres="ANA MARIA", apellidos="PEREZ GOMEZ",
                   fecha_nacimiento="1995-03-15"),
        {"numero_documento": "1.234.567.890", "nombres": "Ana María",
         "apellidos": "Pérez Gómez", "fecha_nacimiento": "1995-03-15"},
    )
    assert r.advertencias == []


def test_palabras_pegadas_y_enie_no_generan_falsa_advertencia():
    r = comparar_con_esperados(
        _resultado(nombres="CARLOSMARIO", apellidos="NUNEZ PENA"),
        {"nombres": "Carlos Mario", "apellidos": "Núñez Peña"},
    )
    assert r.advertencias == []


def test_detecta_documento_y_fecha_distintos():
    r = comparar_con_esperados(
        _resultado(numero_documento="1234567890", fecha_nacimiento="1995-03-15"),
        {"numero_documento": "9999999999", "fecha_nacimiento": "1995-03-16"},
    )
    assert any("documento" in a for a in r.advertencias)
    assert any("nacimiento" in a for a in r.advertencias)
    assert r.to_dict()["coincide"] is False


def test_resultado_serializa_coincide():
    r = ResultadoOCR(disponible=True)
    assert r.to_dict()["coincide"] is True
    r.advertencias = ["algo no coincide"]
    assert r.to_dict()["coincide"] is False


# --------------------------------------------------------------------------
# Sin Tesseract: degrada sin lanzar
# --------------------------------------------------------------------------


def test_sin_tesseract_no_rompe(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr_service, "_TESSERACT_DISPONIBLE", False)
    assert leer_mrz_reverso(tmp_path / "no-existe.jpg") == {}
    r = leer_cedula(tmp_path / "no-existe.jpg", {"numero_documento": "1"})
    assert r.disponible is False and r.advertencias == []
