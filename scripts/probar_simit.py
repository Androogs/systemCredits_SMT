"""
Prueba el estado de cuenta de tránsito (SIMIT vía PlacaPi) contra la
configuración de .env. Requiere SIMIT_API_KEY (pk_live_...).

Uso: python -m scripts.probar_simit --numero-id <documento> [--tipo-id 1]
"""

import argparse

from backend.integrations.simit.client import crear_cliente_simit
from backend.models.enums import TipoIdentificacion


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tipo-id", default="1")
    p.add_argument("--numero-id", required=True)
    a = p.parse_args()
    r = crear_cliente_simit().estado_cuenta_transito(
        TipoIdentificacion(a.tipo_id), a.numero_id
    )
    estado = "PAZ Y SALVO" if r.paz_y_salvo else "CON DEUDA"
    print(f"{estado} | deuda={r.total_deuda} | items={r.total_items} | origen={r.origen}")


if __name__ == "__main__":
    main()
