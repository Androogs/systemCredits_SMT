"""Cargue masivo RUNTPRO desde el Excel de registro de garantías.

CLI del servicio ``registro_garantias_excel_service`` — la misma
lógica que usa el endpoint POST /cargas/garantias-runtpro/excel de la
plataforma (Desembolsos → "Cargue desde registro Excel").

Uso::

    python scripts/cargue_runt_excel.py "C:/ruta/Registro Garantia.xlsx" \
        --hoja 2026 --desde 611 --nit 800235505 --salida salida_runt

Genera el plano oficial ``<NIT>RGM<consecutivo><AAAAMMDD>.txt`` (guía
RUNTPRO GM Fase II) más el Excel de revisión (Garantías + Advertencias).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.db_models.session import SessionLocal  # noqa: E402
from backend.services.registro_garantias_excel_service import (  # noqa: E402
    generar_desde_excel,
)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("archivo", help="Excel de registro de garantías")
    ap.add_argument("--hoja", default="2026", help="hoja del registro")
    ap.add_argument("--desde", type=int, default=1,
                    help="primera fila a leer (default 1: toda la hoja)")
    ap.add_argument("--nit", default=None,
                    help="NIT del acreedor (default: el aliado propio "
                         "de la BD)")
    ap.add_argument("--salida", default="salida_runt",
                    help="directorio de salida")
    args = ap.parse_args()

    contenido = Path(args.archivo).read_bytes()
    with SessionLocal() as db:
        txt, nombre, n_prendas, advertencias, revision, nit, acreedor = (
            generar_desde_excel(
                db,
                contenido=contenido,
                hoja=args.hoja,
                desde=args.desde,
                nit=args.nit,
                generado_por="cargue_excel_registro",
            )
        )
        db.commit()

    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    (salida / nombre).write_bytes(txt)
    nombre_xlsx = nombre.replace(".txt", "_revision.xlsx")
    (salida / nombre_xlsx).write_bytes(revision)

    print(f"Archivo plano : {salida / nombre}")
    print(f"Revisión      : {salida / nombre_xlsx}")
    print(f"Prendas       : {n_prendas}")
    print(f"Acreedor      : {acreedor} NIT {nit}")
    print(f"Advertencias  : {len(advertencias)}")
    for fila, cliente, ced, msg in advertencias:
        print(f"  fila {fila} {cliente} ({ced}): {msg}")
    print("\nVista previa de las primeras líneas:")
    for linea in txt.decode("ascii").splitlines()[:9]:
        print(" ", linea)


if __name__ == "__main__":
    main()
