"""
Smoke test de la API. Primero levanta el servidor desde la raíz:
    .venv\\Scripts\\python.exe -m uvicorn backend.main:app --reload --port 8001
Luego: python -m scripts.probar_api
"""

import json
import os

import httpx

BASE = os.getenv("API_BASE_URL", "http://localhost:8001") + "/api"
PAYLOAD = {
    "tipo_id": "1",
    "numero_id": "1000000001",
    "primer_apellido": "FICTICIO",
    "ocupacion": "Empleado",
    "tipo_contrato": "Indefinido",
    "fecha_nacimiento": "1990-05-15",
    "ingresos_mensuales": 5000000,
    "saldo_financiar": 10000000,
    "plazo": 36,
    "tasa": 2.0,
}


def main() -> None:
    print("GET /health ->", httpx.get(f"{BASE}/health").json())
    escenarios = httpx.get(f"{BASE}/motor/escenarios").json()
    for escenario in escenarios:
        r = httpx.post(f"{BASE}/motor/evaluar", json={**PAYLOAD, "escenario_mock": escenario}, timeout=30)
        data = r.json()
        causales = [c["codigo"] for c in data.get("causales", [])]
        print(f"{escenario:20s} {r.status_code} {data.get('decision')} {causales}")
    print("Auditoría:", len(httpx.get(f"{BASE}/auditoria", params={"limite": 100}).json()), "registros")
    print(json.dumps(httpx.get(f"{BASE}/parametros").json(), indent=2)[:400])


if __name__ == "__main__":
    main()
