"""
Prueba Valor Ingreso contra el ambiente configurado en .env.

Uso: python -m scripts.probar_income --numero-id <documento> [--tipo-id 1]
"""

import argparse
import json

from backend.integrations.datacredito.income_client import IncomeRestClient
from backend.models.enums import TipoIdentificacion


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tipo-id", default="1")
    p.add_argument("--numero-id", required=True)
    a = p.parse_args()
    r = IncomeRestClient().consultar(TipoIdentificacion(a.tipo_id), a.numero_id)
    print(f"Aportantes: {len(r.aportantes)}")
    for ap in r.aportantes:
        print(f"  - {ap.razon_social} | {ap.descripcion_cotizante} | promedio={ap.promedio_ingresos}")
    print(json.dumps(r.model_dump(mode="json"), indent=2, ensure_ascii=False)[:2000])


if __name__ == "__main__":
    main()
