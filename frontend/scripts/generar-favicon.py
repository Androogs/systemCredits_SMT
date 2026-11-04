"""
Genera los favicons de la pestaña a partir de un PNG de marca.

Uso:
    python scripts/generar-favicon.py

Ajusta LOGO_RATIO para cambiar el tamaño del logo dentro del ícono:
    1.00 = el logo toca los bordes (se ve enorme)  <-- ACTUAL
    0.98 = grande, con un pelín de aire
    0.60 = pequeño, con mucho aire
"""

from pathlib import Path

from PIL import Image

# --- Tamaño del logo dentro del ícono (0.0 - 1.0) ---
LOGO_RATIO = 1.00

# --- Archivos de entrada/salida ---
BASE = Path(__file__).resolve().parent.parent
LOGO = BASE / 'public' / 'brand' / 'frontend/public/favicon-sm-192.png'
SALIDAS = {
    'favicon-sm-192.png': 64,
    'favicon-sm-192.png': 192,
}


def generar(logo: Image.Image, size: int) -> Image.Image:
    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    box = int(size * LOGO_RATIO)
    lw, lh = logo.size
    scale = box / max(lw, lh)
    lg = logo.resize((int(lw * scale), int(lh * scale)), Image.LANCZOS)
    canvas.alpha_composite(
        lg, ((size - lg.width) // 2, (size - lg.height) // 2)
    )
    return canvas


def main() -> None:
    logo = Image.open(LOGO).convert('RGBA')
    for nombre, size in SALIDAS.items():
        destino = BASE / 'public' / nombre
        generar(logo, size).save(destino)
        print(f'{nombre} ({size}x{size}) generado')


if __name__ == '__main__':
    main()