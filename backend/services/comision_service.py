"""Comisiones del asesor (D134): 1,3 % del valor desembolsado sin los
gastos administrativos de originación.

Por ahora aplica solo al producto propio (Crédito Directo) — todo
desembolso confirmado hoy lo es; cuando entren comisiones de aliados,
cada uno traerá su porcentaje y este servicio lo leerá por fila."""

from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from backend.auth.dependencies import UsuarioActual
from backend.models.comision_models import (
    ComisionesResponse,
    ComisionFilaResponse,
    ComisionMesResponse,
)
from backend.repositories.comision_repository import ComisionRepository
from backend.repositories.solicitud_repository import _predicado_radicador

# Porcentaje de la comisión del asesor sobre la base (sin gastos adm.).
PCT_COMISION_ASESOR = Decimal("1.3")

_TZ_BOGOTA = ZoneInfo("America/Bogota")


def _mes_bogota(fecha: datetime) -> str:
    """Clave 'YYYY-MM' del desembolso en hora de Colombia. En SQLite la
    fecha vuelve naive: se interpreta como UTC, que es como se guarda."""
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)
    return fecha.astimezone(_TZ_BOGOTA).strftime("%Y-%m")


class ComisionService:
    def __init__(self, db: Session) -> None:
        self._repo = ComisionRepository(db)

    def resumen(self, usuario: UsuarioActual) -> ComisionesResponse:
        """Comisiones sobre desembolsos confirmados. El asesor ve solo
        su producción (mismo alcance por persona que el panel); sin
        ficha el alcance es vacío (fail-closed). El admin ve todo con
        el nombre del radicador en cada fila."""
        vacio = ComisionesResponse(
            porcentaje=PCT_COMISION_ASESOR,
            filas=[],
            meses=[],
            total_desembolsos=0,
            total_capital=Decimal(0),
            total_base=Decimal(0),
            total_comision=Decimal(0),
        )
        predicado = None
        if not usuario.es_admin():
            asesor_ids = usuario.asesor_ids()
            if not asesor_ids:
                return vacio
            predicado = _predicado_radicador(
                asesor_ids, usuario.cedula_asesor, usuario.persona_desde_asesor
            )

        filas: list[ComisionFilaResponse] = []
        meses: dict[str, dict] = {}
        total_capital = Decimal(0)
        total_base = Decimal(0)
        total_comision = Decimal(0)
        for desembolso, credito, solicitud, cliente, nombre_asesor in (
            self._repo.desembolsos(predicado)
        ):
            capital = Decimal(str(desembolso.capital or 0))
            base = max(
                capital - Decimal(str(credito.gastos_administrativos or 0)),
                Decimal(0),
            )
            comision = (base * PCT_COMISION_ASESOR / 100).quantize(
                Decimal("0.01")
            )
            filas.append(
                ComisionFilaResponse(
                    id_desembolso=desembolso.id_desembolso,
                    num_desembolso=desembolso.num_desembolso,
                    num_solicitud=solicitud.num_solicitud,
                    nombre_cliente=cliente.nombre_completo,
                    nombre_asesor=(
                        nombre_asesor if usuario.es_admin() else None
                    ),
                    fecha_desembolso=desembolso.fecha_desembolso,
                    capital=capital,
                    base=base,
                    comision=comision,
                )
            )
            clave = (
                _mes_bogota(desembolso.fecha_desembolso)
                if desembolso.fecha_desembolso
                else "sin-fecha"
            )
            mes = meses.setdefault(
                clave,
                {
                    "desembolsos": 0,
                    "capital": Decimal(0),
                    "comision": Decimal(0),
                },
            )
            mes["desembolsos"] += 1
            mes["capital"] += capital
            mes["comision"] += comision
            total_capital += capital
            total_base += base
            total_comision += comision

        return ComisionesResponse(
            porcentaje=PCT_COMISION_ASESOR,
            filas=filas,
            meses=[
                ComisionMesResponse(
                    mes=clave,
                    desembolsos=m["desembolsos"],
                    capital=m["capital"],
                    comision=m["comision"],
                )
                for clave, m in sorted(meses.items(), reverse=True)
            ],
            total_desembolsos=len(filas),
            total_capital=total_capital,
            total_base=total_base,
            total_comision=total_comision,
        )
