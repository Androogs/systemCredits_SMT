"""OCR de la cédula en el flujo de captura (paso 3 del wizard).

Dibuja cédulas SINTÉTICAS (datos ficticios) con PIL, las sube por el endpoint
público de captura y verifica el resultado fusionado en la sesión del asesor.

- Las pruebas que requieren el binario de Tesseract se marcan con ``skipif``.
- ``test_fotos_reales`` corre solo si se define ``OCR_CEDULAS_DIR`` (carpeta
  local, FUERA del repositorio, con fotos reales y un ``esperado.json``; ver
  ``scripts/probar_ocr_cedula.py``). Así se valida con cédulas reales sin
  versionar datos personales.
"""

import io
import json
import os
from pathlib import Path

import pytest

from backend.services import ocr_service

tesseract_instalado = pytest.mark.skipif(
    not ocr_service._TESSERACT_DISPONIBLE,
    reason="Tesseract no está instalado en este entorno",
)

_FUENTES = ("DejaVuSans.ttf", "arial.ttf", "Arial.ttf", "LiberationSans-Regular.ttf")
_FUENTES_MONO = ("DejaVuSansMono.ttf", "cour.ttf", "LiberationMono-Regular.ttf")


def _fuente(nombres, tamano):
    from PIL import ImageFont

    for nombre in nombres:
        try:
            return ImageFont.truetype(nombre, tamano)
        except OSError:
            continue
    pytest.skip("No hay fuente TrueType para dibujar la cédula sintética")


def _png(img) -> bytes:
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def _anverso_blanca(nuip: str = "1.234.567.890") -> bytes:
    """Maqueta de la cédula blanca: rótulo pequeño encima del valor."""
    from PIL import Image, ImageDraw

    rotulo, valor, titulo = _fuente(_FUENTES, 22), _fuente(_FUENTES, 34), _fuente(_FUENTES, 46)
    img = Image.new("RGB", (1500, 1000), (90, 90, 90))  # mesa oscura
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([60, 80, 1440, 950], radius=30, fill="white")
    d.text((520, 110), "REPÚBLICA DE COLOMBIA", fill=(170, 40, 40), font=titulo)
    d.rectangle([110, 210, 470, 700], fill=(200, 200, 200))  # foto
    filas = [
        (200, "Apellidos", "PEREZ GOMEZ"),
        (300, "Nombres", "ANA MARIA"),
        (500, "Fecha de nacimiento", "15 MAR 1995"),
        (600, "Lugar de nacimiento", "CALI (VALLE)"),
        (700, "Fecha y lugar de expedición", "20 ENE 2021, CALI"),
        (800, "Fecha de expiración", "15 MAR 2035"),
    ]
    for y, r, v in filas:
        d.text((520, y), r, fill=(90, 90, 90), font=rotulo)
        d.text((520, y + 30), v, fill="black", font=valor)
    d.text((1000, 200), "NUIP", fill=(90, 90, 90), font=valor)
    d.text((1100, 200), nuip, fill="black", font=valor)
    d.text((520, 400), "Nacionalidad", fill=(90, 90, 90), font=rotulo)
    d.text((760, 400), "Estatura", fill=(90, 90, 90), font=rotulo)
    d.text((920, 400), "Sexo", fill=(90, 90, 90), font=rotulo)
    d.text((520, 430), "COL", fill="black", font=valor)
    d.text((760, 430), "1.62", fill="black", font=valor)
    d.text((920, 430), "F", fill="black", font=valor)
    return _png(img)


def _reverso_blanca() -> bytes:
    """Reverso con MRZ ficticio y dígitos de control válidos."""
    from PIL import Image, ImageDraw

    mono = _fuente(_FUENTES_MONO, 46)
    img = Image.new("RGB", (1500, 1000), (90, 90, 90))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([60, 80, 1440, 950], radius=30, fill="white")
    d.rectangle([1100, 120, 1400, 420], fill="black")  # QR
    for i, linea in enumerate((
        "ICCOL012345678498765<<<<<<<<<<",
        "9503157F3503155COL1234567890<2",
        "PEREZ<GOMEZ<<ANA<MARIA<<<<<<<<",
    )):
        d.text((110, 640 + i * 80), linea, fill="black", font=mono)
    return _png(img)


def _subir(client, token: str, tipo: str, contenido: bytes):
    return client.post(
        f"/api/captura/{token}/evidencias",
        data={"tipo": tipo},
        files={"archivo": (f"{tipo}.png", io.BytesIO(contenido), "image/png")},
    )


@tesseract_instalado
def test_ocr_fusiona_anverso_y_reverso_sin_advertencias(client):
    sesion = client.post(
        "/api/sesiones-captura",
        json={
            "numero_documento": "1234567890",
            "nombres": "Ana María",
            "apellidos": "Pérez Gómez",
            "fecha_nacimiento": "1995-03-15",
        },
    ).json()
    # El reverso llega primero: la fusión no depende del orden.
    assert _subir(client, sesion["token"], "cedula_reverso", _reverso_blanca()).status_code == 201
    assert _subir(client, sesion["token"], "cedula_frontal", _anverso_blanca()).status_code == 201

    ocr = client.get(f"/api/sesiones-captura/{sesion['id_sesion']}").json()["ocr"]
    assert ocr["disponible"] is True
    assert ocr["tipo_cedula"] == "blanca"
    assert ocr["numero_documento"]["valor"] == "1234567890"
    assert ocr["numero_documento"]["fuente"] == "mrz"
    assert ocr["nombres"]["valor"] in ("ANA MARIA", "ANA MARÍA")
    assert ocr["apellidos"]["valor"] == "PEREZ GOMEZ"
    assert ocr["fecha_nacimiento"]["valor"] == "1995-03-15"
    assert ocr["sexo"]["valor"] == "F"
    assert ocr["lugar_nacimiento"]["valor"] == "CALI (VALLE)"
    assert ocr["fecha_expedicion"]["valor"] == "2021-01-20"
    assert ocr["ciudad_expedicion"]["valor"] == "CALI"
    assert ocr["coincide"] is True, ocr["advertencias"]
    assert set(ocr["lecturas"]) == {"cedula_frontal", "cedula_reverso"}


@tesseract_instalado
def test_ocr_advierte_cedula_distinta(client):
    sesion = client.post("/api/sesiones-captura", json={"numero_documento": "9999999999"}).json()
    _subir(client, sesion["token"], "cedula_frontal", _anverso_blanca())

    ocr = client.get(f"/api/sesiones-captura/{sesion['id_sesion']}").json()["ocr"]
    assert ocr["coincide"] is False
    assert any("documento" in aviso.lower() for aviso in ocr["advertencias"])


@tesseract_instalado
def test_endpoint_publico_no_expone_datos_del_ocr(client):
    """El celular del cliente solo ve si la cédula fue legible, no los datos."""
    sesion = client.post("/api/sesiones-captura", json={"numero_documento": "1234567890"}).json()
    _subir(client, sesion["token"], "cedula_frontal", _anverso_blanca())

    publico = client.get(f"/api/captura/{sesion['token']}").json()
    assert "ocr" not in publico
    assert publico["cedula_legible"] == {"cedula_frontal": True}


def test_ocr_no_rompe_con_imagen_ilegible(client):
    """Una imagen sin texto no debe tumbar la subida: OCR best-effort."""
    from PIL import Image

    sesion = client.post("/api/sesiones-captura", json={}).json()
    buffer = io.BytesIO()
    Image.new("RGB", (200, 120), "white").save(buffer, format="PNG")

    assert _subir(client, sesion["token"], "cedula_frontal", buffer.getvalue()).status_code == 201
    estado = client.get(f"/api/sesiones-captura/{sesion['id_sesion']}").json()
    assert estado["ocr"] is not None
    assert estado["ocr"]["coincide"] is True  # sin campos leídos no hay diferencias


# --------------------------------------------------------------------------
# Fotos reales (opcional, fuera del repositorio)
# --------------------------------------------------------------------------

_DIR_REAL = os.environ.get("OCR_CEDULAS_DIR")


@tesseract_instalado
@pytest.mark.skipif(not _DIR_REAL, reason="Definir OCR_CEDULAS_DIR para probar con fotos reales")
def test_fotos_reales():
    """``esperado.json``: {"foto.jpeg": {"numero_documento": "...", ...}, ...}."""
    carpeta = Path(_DIR_REAL)
    esperado = json.loads((carpeta / "esperado.json").read_text(encoding="utf-8"))
    fallos = []
    for archivo, campos in esperado.items():
        lectura = ocr_service.analizar_cara(carpeta / archivo)
        for campo, valor in campos.items():
            leido = getattr(lectura, campo, None) if campo in ("tipo_cedula", "cara") else (
                lectura.campos.get(campo).valor if campo in lectura.campos else ""
            )
            if leido != valor:
                fallos.append(f"{archivo}: {campo} = {leido!r}, esperado {valor!r}")
    assert not fallos, "\n".join(fallos)
