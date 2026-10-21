"""Respuestas SIMIT FICTICIAS para el ambiente demo (sin API key de
PlacaPi). Nunca se usan en ambiente "produccion".

- "simit_multas": deuda pendiente — dispara el rechazo R22 sin
  consumir el escenario de buró.
- cualquier otro: paz y salvo, la evaluación sigue al buró.
"""

from decimal import Decimal

from backend.integrations.simit.client import ResultadoSimit

ESCENARIO_SIMIT_MULTAS = "simit_multas"


def resultado_mock(escenario: str | None) -> ResultadoSimit:
    if escenario == ESCENARIO_SIMIT_MULTAS:
        return ResultadoSimit(
            paz_y_salvo=False,
            total_deuda=Decimal("850000"),
            total_items=2,
            origen=f"mock:{escenario}",
        )
    return ResultadoSimit(
        paz_y_salvo=True,
        total_deuda=Decimal(0),
        total_items=0,
        origen="mock:limpio",
    )
