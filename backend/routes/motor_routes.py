"""Endpoints del motor de decisión."""

import json
from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile

from backend.integrations.datacredito.mock_buro import ESCENARIOS
from backend.integrations.datacredito.parsers.hdc_parser import HDCParser
from backend.integrations.datacredito.parsers.income_parser import IncomeParser
from backend.models.motor_models import (
    EvaluarRequest,
    IngresoPropioRequest,
    IngresoPropioResponse,
    ResultadoMotorResponse,
    Solicitud,
)
from backend.routes.dependencies import get_evaluacion_service
from backend.services.evaluacion_service import EvaluacionService

router = APIRouter(prefix="/motor", tags=["motor"])


@router.post("/evaluar", response_model=ResultadoMotorResponse)
def evaluar(
    payload: EvaluarRequest,
    servicio: EvaluacionService = Depends(get_evaluacion_service),
) -> ResultadoMotorResponse:
    """Evalúa una solicitud enviada completa en el payload y la registra en auditoría."""
    resultado = servicio.evaluar_payload(payload)
    return ResultadoMotorResponse.desde_resultado(resultado, incluir_detalle_buro=True)


@router.post("/ingreso", response_model=IngresoPropioResponse)
def ingreso_propio(
    payload: IngresoPropioRequest,
    servicio: EvaluacionService = Depends(get_evaluacion_service),
) -> IngresoPropioResponse:
    """Valor Ingreso calculado con los cotizantes almacenados de la solicitud."""
    return servicio.calcular_ingreso_propio(payload)


@router.get("/escenarios")
def escenarios() -> dict[str, str]:
    """Escenarios ficticios disponibles en ambiente demo."""
    return ESCENARIOS


@router.post("/evaluar-con-archivos", response_model=ResultadoMotorResponse)
def evaluar_con_archivos(
    hdc_file: UploadFile = File(..., description="JSON o PDF de Historia de Crédito+"),
    income_file: UploadFile = File(None, description="JSON o PDF de Valor Ingreso (opcional)"),
    tipo_id: str = Form(...),
    numero_id: str = Form(...),
    primer_apellido: str = Form(...),
    ocupacion: str = Form(...),
    tipo_contrato: str | None = Form(None),
    antiguedad_meses: int | None = Form(None),
    anios_camara_comercio: float | None = Form(None),
    fecha_nacimiento: str = Form(...),
    ingresos_mensuales: float = Form(0),
    otros_ingresos: float = Form(0),
    saldo_financiar: float = Form(...),
    plazo: int = Form(...),
    tasa: float = Form(...),
    servicio: EvaluacionService = Depends(get_evaluacion_service),
) -> ResultadoMotorResponse:
    """Evalúa una solicitud con reportes de Experian cargados como archivos."""
    # Leer archivos
    hdc_content = hdc_file.file.read()
    hdc_json = leer_reporte_from_bytes(hdc_content, hdc_file.filename)

    income_json = None
    if income_file:
        income_content = income_file.file.read()
        income_json = leer_reporte_from_bytes(income_content, income_file.filename)

    # Crear solicitud
    solicitud = Solicitud(
        tipo_id=tipo_id,
        numero_id=numero_id,
        primer_apellido=primer_apellido,
        ocupacion=ocupacion,
        tipo_contrato=tipo_contrato,
        antiguedad_meses=antiguedad_meses,
        anios_camara_comercio=anios_camara_comercio,
        fecha_nacimiento=fecha_nacimiento,
        ingresos_mensuales=ingresos_mensuales,
        otros_ingresos=otros_ingresos,
        saldo_financiar=saldo_financiar,
        plazo=plazo,
        tasa=tasa,
    )

    # Parsear reportes
    hdc = HDCParser().parse(hdc_json)
    vi = IncomeParser().parse(income_json) if income_json is not None else None

    # Evaluar
    resultado = servicio.evaluar_con_reportes(solicitud, hdc, vi)
    return ResultadoMotorResponse.desde_resultado(resultado, incluir_detalle_buro=True)


def leer_reporte_from_bytes(content: bytes, filename: str) -> dict[str, Any]:
    """Lee un reporte desde bytes (JSON o PDF)."""
    import io

    from pypdf import PdfReader

    # Intentar como JSON primero
    try:
        return json.loads(content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass

    # Si no es JSON, intentar como PDF
    try:
        pdf_file = io.BytesIO(content)
        reader = PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        # Buscar JSON en el texto del PDF
        import re

        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            return json.loads(json_match.group())
        raise ValueError("No se encontró JSON válido en el PDF")
    except Exception as e:
        raise ValueError(f"No se pudo leer el archivo {filename}: {e}") from e
