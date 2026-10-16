"""Imagen → líneas OCR: carga, localización de la tarjeta y pasadas de Tesseract.

Por qué así (medido con fotos reales de celular):

- **Recorte geométrico** (contorno con proporción ID-1 = 85,6 × 54 mm ≈ 1,586):
  funciona cuando hay contraste tarjeta/fondo (cédula amarilla sobre mesa
  oscura). Exigir la proporción evita recortar el teclado u otro objeto.
- **Recorte guiado por texto**: cuando la tarjeta es blanca sobre una mesa
  clara no hay borde aprovechable. Se hace una pasada dispersa sobre la foto
  completa, se ubican rótulos de la cédula (REPÚBLICA, NUIP, APELLIDOS, MRZ…)
  y se recorta alrededor.
- **Sin umbral fijo**: el umbral en 150 destruía el texto sobre el holograma
  de la amarilla. LSTM lee mejor en gris; además se prueba una variante con el
  fondo normalizado (divide por el fondo estimado), que es la que mejor lee la
  amarilla.
- **Escalado**: el texto debe medir ~30 px de alto; una foto comprimida por
  WhatsApp trae la tarjeta en ~600 px de ancho, así que se amplía a 1800 px.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Tuple, List

from backend.services.ocr_parser import Linea, Palabra, claves_de_token

logger = logging.getLogger("creditos.ocr")

try: # pragma: no cover - depende del entorno
    import cv2
    import numpy as np

    _OPENCV_DISPONIBLE = True
except Exception: # noqa: BLE001
    cv2 = None # type: ignore[assignment]
    np = None # type: ignore[assignment]
    _OPENCV_DISPONIBLE = False

try: # pragma: no cover - depende del entorno
    import pytesseract
    from PIL import Image, ImageOps

    _TESSERACT_IMPORTADO = True
except Exception: # noqa: BLE001
    pytesseract = None # type: ignore[assignment]
    Image = None # type: ignore[assignment]
    ImageOps = None # type: ignore[assignment]
    _TESSERACT_IMPORTADO = False

try: # pragma: no cover - opcional: fotos HEIC/HEIF de iPhone
    import pillow_heif # type: ignore[import-untyped]
    pillow_heif.register_heif_opener()
except Exception: # noqa: BLE001
    pass

PROPORCION_ID1 = 85.6 / 53.98
ANCHO_TRABAJO_PX = 1800
_AMPLIACION_MAXIMA = 4.0
LISTA_BLANCA_MRZ = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"

@dataclass
class Recorte:
    imagen: Any # escala de grises, horizontal
    metodo: str # geometria | texto | completa

# --------------------------------------------------------------------------
# Carga
# --------------------------------------------------------------------------

def cargar_imagen(ruta: Path) -> Any:
    """RGB como arreglo numpy, respetando la orientación EXIF del celular."""
    with Image.open(ruta) as original: # type: ignore[union-attr]
        imagen = ImageOps.exif_transpose(original) # type: ignore[union-attr]
        imagen = imagen.convert("RGB")
        return np.array(imagen)

def a_gris(rgb: Any) -> Any:
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

# --------------------------------------------------------------------------
# Localización geométrica
# --------------------------------------------------------------------------

def _ordenar_esquinas(pts: Any) -> Any:
    """(sup-izq, sup-der, inf-der, inf-izq)."""
    suma = pts.sum(axis=1)
    dif = np.diff(pts, axis=1).ravel()
    return np.array(
        [pts[np.argmin(suma)], pts[np.argmin(dif)], pts[np.argmax(suma)], pts[np.argmax(dif)]],
        dtype=np.float32,
    )

def _enderezar(imagen: Any, esquinas: Any) -> Any:
    tl, tr, br, bl = _ordenar_esquinas(esquinas)
    ancho = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
    alto = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
    destino = np.array([[0, 0], [ancho - 1, 0], [ancho - 1, alto - 1], [0, alto - 1]], np.float32)
    matriz = cv2.getPerspectiveTransform(np.array([tl, tr, br, bl], np.float32), destino)
    return cv2.warpPerspective(imagen, matriz, (ancho, alto))

def localizar_por_geometria(rgb: Any) -> Optional[Any]:
    """Recorte enderezado de la tarjeta o None si no hay un contorno creíble."""
    alto, ancho = rgb.shape[:2]
    escala = 1000 / max(alto, ancho)
    chica = cv2.resize(rgb, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA)
    gris = cv2.cvtColor(chica, cv2.COLOR_RGB2GRAY)
    hsv = cv2.cvtColor(chica, cv2.COLOR_RGB2HSV)
    area_total = gris.shape[0] * gris.shape[1]
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))

    mapas = []
    suave = cv2.GaussianBlur(gris, (5, 5), 0)
    for bajo, alto_c in ((20, 60), (40, 120), (60, 160)):
        mapas.append((cv2.Canny(suave, bajo, alto_c), cv2.RETR_LIST))
    _, otsu = cv2.threshold(
        cv2.GaussianBlur(hsv[..., 2], (7, 7), 0), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    mapas.append((otsu, cv2.RETR_EXTERNAL))

    mejor = None
    for mapa, modo in mapas:
        cerrado = cv2.morphologyEx(mapa, cv2.MORPH_CLOSE, kernel, iterations=2)
        contornos, _ = cv2.findContours(cerrado, modo, cv2.CHAIN_APPROX_SIMPLE)
        for contorno in contornos:
            area = cv2.contourArea(contorno)
            if not (0.03 * area_total < area < 0.92 * area_total):
                continue
            rect = cv2.minAreaRect(contorno)
            w, h = rect[1]
            if min(w, h) < 1:
                continue
            proporcion = max(w, h) / min(w, h)
            llenado = area / (w * h)
            if not (1.40 < proporcion < 1.80) or llenado < 0.85:
                continue
            puntaje = llenado - abs(proporcion - PROPORCION_ID1) + min(area / area_total, 0.5)
            if mejor is None or puntaje > mejor[0]:
                perimetro = cv2.arcLength(contorno, True)
                aprox = cv2.approxPolyDP(contorno, 0.02 * perimetro, True)
                esquinas = aprox.reshape(-1, 2) if len(aprox) == 4 else cv2.boxPoints(rect)
                mejor = (puntaje, esquinas.astype(np.float32) / escala)
    if mejor is None:
        return None
    recorte = _enderezar(rgb, mejor[1])
    if recorte.shape[0] < 60 or recorte.shape[1] < 60:
        return None
    return a_gris(recorte)

# --------------------------------------------------------------------------
# Localización guiada por texto
# --------------------------------------------------------------------------

def _es_ancla(texto: str) -> bool:
    limpio = texto.strip()
    if "<<" in limpio and len(limpio) >= 10:
        return True # línea MRZ
    digitos = sum(c.isdigit() for c in limpio)
    if digitos >= 7 and ("." in limpio or "-" in limpio):
        return True # 1.006.461.914 o P-3107900-...
    return bool(claves_de_token(limpio)) and len(limpio) >= 4

def localizar_por_texto(
    gris: Any, idioma: str, timeout: int
) -> Tuple[Optional[Any], int]:
    """Recorta alrededor de los rótulos de la cédula hallados en la foto completa."""
    alto, ancho = gris.shape[:2]
    escala = min(2000 / max(alto, ancho), _AMPLIACION_MAXIMA)
    trabajo = cv2.resize(gris, None, fx=escala, fy=escala, interpolation=cv2.INTER_CUBIC)
    datos = pytesseract.image_to_data( # type: ignore[union-attr]
        trabajo, lang=idioma, config="--oem 1 --psm 11", timeout=timeout,
        output_type=pytesseract.Output.DICT, # type: ignore[union-attr]
    )
    cajas = []
    for i, texto in enumerate(datos["text"]):
        try:
            conf = float(datos["conf"][i])
        except (TypeError, ValueError):
            continue
        if conf < 30 or not texto or not _es_ancla(texto):
            continue
        cajas.append((
            datos["left"][i], datos["top"][i],
            datos["left"][i] + datos["width"][i], datos["top"][i] + datos["height"][i],
        ))
    if len(cajas) < 2:
        return None, len(cajas)
    arr = np.array(cajas, dtype=float) / escala
    x0, y0 = arr[:, 0].min(), arr[:, 1].min()
    x1, y1 = arr[:, 2].max(), arr[:, 3].max()
    margen = 0.25 * max(x1 - x0, y1 - y0)
    x0, y0 = int(max(0, x0 - margen)), int(max(0, y0 - margen))
    x1, y1 = int(min(ancho, x1 + margen)), int(min(alto, y1 + margen))
    if x1 - x0 < 60 or y1 - y0 < 30:
        return None, len(cajas)
    return gris[y0:y1, x0:x1], len(cajas)

def rotacion_osd(gris: Any, timeout: int) -> int:
    """Rotación (0/90/180/270) que sugiere el OSD de Tesseract; 0 si no sabe."""
    try:
        salida = pytesseract.image_to_osd( # type: ignore[union-attr]
            gris, config="--psm 0", timeout=timeout
        )
    except Exception: # noqa: BLE001
        return 0
    for linea in salida.splitlines():
        if linea.startswith("Rotate:"):
            try:
                return int(linea.split(":")[1]) % 360
            except ValueError:
                return 0
    return 0

def rotar(gris: Any, grados: int) -> Any:
    if grados == 90:
        return cv2.rotate(gris, cv2.ROTATE_90_CLOCKWISE)
    if grados == 180:
        return cv2.rotate(gris, cv2.ROTATE_180)
    if grados == 270:
        return cv2.rotate(gris, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return gris

def a_horizontal(gris: Any) -> Any:
    if gris.shape[0] > gris.shape[1]:
        return rotar(gris, 90)
    return gris

# --------------------------------------------------------------------------
# Preprocesamiento y Tesseract
# --------------------------------------------------------------------------

def escalar(gris: Any, ancho: int = ANCHO_TRABAJO_PX) -> Any:
    factor = min(ancho / gris.shape[1], _AMPLIACION_MAXIMA)
    if abs(factor - 1) < 0.05:
        return gris
    interpolacion = cv2.INTER_CUBIC if factor > 1 else cv2.INTER_AREA
    return cv2.resize(gris, None, fx=factor, fy=factor, interpolation=interpolacion)

def variante(gris: Any, modo: str) -> Any:
    """gris | fondo (normaliza iluminación y atenúa hologramas)."""
    if modo == "fondo":
        fondo = cv2.medianBlur(cv2.dilate(gris, np.ones((7, 7), np.uint8)), 31)
        return cv2.divide(gris, fondo, scale=255)
    return gris

def ocr_lineas(
    imagen: Any, idioma: str, psm: int, timeout: int, lista_blanca: Optional[str] = None
) -> List[Linea]:
    """Una pasada de Tesseract → líneas con palabras, confianza y posición 0-1."""
    config = f"--oem 1 --psm {psm}"
    if lista_blanca:
        config += f" -c tessedit_char_whitelist={lista_blanca}"
    datos = pytesseract.image_to_data( # type: ignore[union-attr]
        imagen, lang=idioma, config=config, timeout=timeout,
        output_type=pytesseract.Output.DICT, # type: ignore[union-attr]
    )
    alto, ancho = imagen.shape[:2]
    grupos: dict[tuple[int, int, int], list[Palabra]] = {}
    for i, texto in enumerate(datos["text"]):
        texto = (texto or "").strip()
        if not texto:
            continue
        try:
            conf = float(datos["conf"][i])
        except (TypeError, ValueError):
            continue
        if conf < 0:
            continue
        clave = (datos["block_num"][i], datos["par_num"][i], datos["line_num"][i])
        grupos.setdefault(clave, []).append(
            Palabra(
                texto=texto,
                conf=conf,
                x0=datos["left"][i] / ancho,
                y0=datos["top"][i] / alto,
                x1=(datos["left"][i] + datos["width"][i]) / ancho,
                y1=(datos["top"][i] + datos["height"][i]) / alto,
            )
        )
    lineas = [Linea(sorted(p, key=lambda w: w.x0)) for p in grupos.values()]
    lineas.sort(key=lambda ln: ln.y)
    return lineas

def texto_de(lineas: List[Linea]) -> str:
    return "\n".join(ln.texto for ln in lineas)