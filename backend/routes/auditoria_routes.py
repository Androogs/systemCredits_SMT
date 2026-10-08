"""Consulta de la auditoría de evaluaciones."""

import json
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db_models.session import get_db
from backend.models.enums import DecisionFinal
from backend.repositories.auditoria_repository import AuditoriaRepository
from backend.services.motor_exceptions import SolicitudNoEncontradaError

router = APIRouter(prefix="/auditoria", tags=["auditoria"])


class EvaluacionResumen(BaseModel):
    evaluacion_id: str
    fecha_evaluacion: str
    origen_datos: str
    parametros_huella: str | None
    id_solicitud: str | None
    numero_id: str
    ocupacion: str
    edad: int
    decision: str
    decision_interna: str
    causales: list[dict[str, Any]]
    tiempo_ms: int


def _resumen(e) -> EvaluacionResumen:
    return EvaluacionResumen(
        evaluacion_id=e.evaluacion_id,
        fecha_evaluacion=e.fecha_evaluacion.isoformat(),
        origen_datos=e.origen_datos,
        parametros_huella=e.parametros_huella,
        id_solicitud=e.id_solicitud,
        numero_id=e.numero_id,
        ocupacion=e.ocupacion,
        edad=e.edad,
        decision=e.decision,
        decision_interna=e.decision_interna,
        causales=json.loads(e.causales),
        tiempo_ms=e.tiempo_ms,
    )


@router.get("", response_model=list[EvaluacionResumen])
def listar(
    limite: int = Query(50, ge=1, le=500),
    numero_id: str | None = None,
    decision: DecisionFinal | None = None,
    id_solicitud: str | None = None,
    db: Session = Depends(get_db),
) -> list[EvaluacionResumen]:
    registros = AuditoriaRepository(db).listar(
        limite=limite,
        numero_id=numero_id,
        decision=decision.value if decision else None,
        id_solicitud=id_solicitud,
    )
    return [_resumen(e) for e in registros]


@router.get("/{evaluacion_id}")
def detalle(evaluacion_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    e = AuditoriaRepository(db).obtener(evaluacion_id)
    if e is None:
        raise SolicitudNoEncontradaError("Evaluación no encontrada")
    return {
        **_resumen(e).model_dump(),
        "ambiente": e.ambiente,
        "request": json.loads(e.request_json),
        "resultado": json.loads(e.resultado_json),
    }
