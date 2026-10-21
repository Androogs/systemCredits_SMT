"""D97 — Benchmark del motor de decisión: costo por evaluación.

Dos niveles con los 13 escenarios del buró mock:

- `evaluar_con_reportes` (sin DB): validación de identidad + reglas de
  consistencia + motor puro — el costo de la decisión con el reporte
  de buró ya en memoria.
- `POST /solicitudes/{id}/evaluar` end-to-end: SIMIT mock + escenario +
  persistencia completa (evaluación, capacidad de pago, causales,
  ofertas, auditoría) — el costo por request medido sobre SQLite en
  memoria; en Postgres producción se suma la latencia de red a BD.

Los números impresos alimentan BENCHMARK_MOTOR.md. El guard solo caza
regresiones groseras (p95 por encima de un orden de magnitud); no es
un SLA y en CI puede variar por la máquina.
"""

import statistics
import time
from decimal import Decimal

import pytest

from backend.config import Settings
from backend.integrations.datacredito.mock_buro import ESCENARIOS, crear_escenario
from backend.models.motor_models import EvaluarRequest
from backend.services.evaluacion_service import EvaluacionService
from backend.services.motor_parametros import ParametrosStore

CALENTAMIENTO = 10
ITERACIONES = 100
# Los guards son una red anti-regresión burda, no un SLA.
GUARD_P95_PURO_MS = 500
GUARD_P95_ENDPOINT_MS = 1_500

SOLICITUD = {
    "cliente": {
        "tipo_documento": "1",
        "num_cedula": "1000000001",
        "nombre_completo": "Cliente Ficticio",
        "primer_apellido": "Ficticio",
        "fecha_nacimiento": "1990-05-15",
        "ocupacion": "Empleado",
    },
    "datos_laborales": {"tipo_contrato": "Indefinido", "ingreso_mensual": 5000000},
}
ITERACIONES_ENDPOINT = 25


def _medir(
    fn, iteraciones: int, calentamiento: int = CALENTAMIENTO
) -> dict[str, float]:
    for _ in range(calentamiento):
        fn()
    muestras = []
    for _ in range(iteraciones):
        t0 = time.perf_counter()
        fn()
        muestras.append((time.perf_counter() - t0) * 1_000)
    q = statistics.quantiles(muestras, n=100)
    return {
        "n": iteraciones,
        "media": statistics.fmean(muestras),
        "p50": q[49],
        "p95": q[94],
        "p99": q[98],
        "min": min(muestras),
        "max": max(muestras),
    }


def _fila(nombre: str, m: dict[str, float]) -> str:
    return (
        f"{nombre:<22} n={m['n']:>4}  media={m['media']:6.2f}  "
        f"p50={m['p50']:6.2f}  p95={m['p95']:6.2f}  p99={m['p99']:6.2f}  "
        f"min={m['min']:6.2f}  max={m['max']:6.2f}"
    )


def test_benchmark_motor_puro(tmp_path):
    """evaluar_con_reportes por escenario, sin DB ni red."""
    settings = Settings(
        environment="demo",
        smmlv=1_300_000,
        parametros_path=tmp_path / "parametros.json",
    )
    svc = EvaluacionService(
        db=None,
        settings=settings,
        store=ParametrosStore(settings.parametros_path),
    )
    solicitud = EvaluarRequest(
        tipo_id="1",
        numero_id="1000000001",
        primer_apellido="Ficticio",
        ocupacion="Empleado",
        tipo_contrato="Indefinido",
        fecha_nacimiento="1990-05-15",
        ingresos_mensuales=Decimal(5_000_000),
        saldo_financiar=Decimal(10_000_000),
        plazo=36,
        tasa=Decimal(2),
    ).a_solicitud()

    print("\n\nBenchmark motor puro (evaluar_con_reportes) — ms por evaluación")
    peor_p95 = 0.0
    for escenario in sorted(ESCENARIOS):
        hdc, vi = crear_escenario(
            escenario,
            solicitud.tipo_id,
            solicitud.numero_id,
            solicitud.primer_apellido,
            settings.smmlv,
        )
        m = _medir(
            lambda: svc.evaluar_con_reportes(solicitud, hdc, vi),
            ITERACIONES,
        )
        peor_p95 = max(peor_p95, m["p95"])
        print(_fila(escenario, m))
    assert peor_p95 < GUARD_P95_PURO_MS


@pytest.mark.parametrize("escenario", ["aprobado", "mora_90"])
def test_benchmark_evaluar_endpoint(client, escenario):
    """POST /evaluar end-to-end con persistencia (ofertas solo en aprobado)."""
    calentamiento = 5
    ids = []
    for _ in range(ITERACIONES_ENDPOINT + calentamiento):
        r = client.post("/api/solicitudes", json=SOLICITUD)
        assert r.status_code == 201, r.text
        ids.append(r.json()["id_solicitud"])

    tiempos = _medir(
        lambda: client.post(
            f"/api/solicitudes/{ids.pop(0)}/evaluar",
            json={
                "saldo_financiar": 10_000_000,
                "plazo": 36,
                "tasa": 2,
                "escenario_mock": escenario,
            },
        ).raise_for_status(),
        ITERACIONES_ENDPOINT,
        calentamiento,
    )
    print(f"\nBenchmark endpoint POST /evaluar [{escenario}]")
    print(_fila("end-to-end", tiempos))
    assert tiempos["p95"] < GUARD_P95_ENDPOINT_MS
