"""
Prueba HDC+ contra el ambiente configurado en .env.

Uso: python -m scripts.probar_hdc --tipo-id 1 --numero-id <documento> --apellido <APELLIDO>
"""

import argparse
import json

from backend.integrations.datacredito.hdc_client import HDCRestClient
from backend.models.enums import TipoIdentificacion


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tipo-id", default="1")
    p.add_argument("--numero-id", required=True)
    p.add_argument("--apellido", required=True)
    a = p.parse_args()
    r = HDCRestClient().consultar(TipoIdentificacion(a.tipo_id), a.numero_id, a.apellido)
    print(f"Código: {r.respuesta_codigo} - {r.respuesta_desc}")
    print(f"Scores: {[(s.tipo, str(s.puntaje)) for s in r.scores]}")
    print(f"Quanto: {r.quanto.valor_medio if r.quanto else None} (miles)")
    print(f"Cartera: {len(r.cuentas_cartera)} | Tarjetas: {len(r.tarjetas_credito)}")
    print(json.dumps(r.model_dump(mode="json"), indent=2, ensure_ascii=False)[:2000])


if __name__ == "__main__":
    main()
