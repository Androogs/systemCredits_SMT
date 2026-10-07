"""
Evalúa localmente una solicitud con reportes de Experian exportados
(JSON o PDF que contiene el JSON), sin llamar servicios remotos ni
escribir en base de datos.

Uso (desde la raíz del proyecto):
    python -m scripts.evaluar_local --solicitud ejemplos/solicitud_ejemplo.json \
        --hdc ruta/hdc.json --ingresos ruta/valor_ingreso.json --salida resultado.json

Si el archivo de solicitud no existe, se crea preguntando en la
terminal los datos que no vienen en los reportes.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from backend.integrations.datacredito.parsers.hdc_parser import HDCParser
from backend.integrations.datacredito.parsers.income_parser import IncomeParser
from backend.models.motor_models import ResultadoMotor, Solicitud
from backend.services.evaluacion_service import EvaluacionService
from backend.services.motor_exceptions import MotorError
from backend.utils.lectura_reportes import leer_reporte


def evaluar(
    solicitud_json: dict[str, Any],
    hdc_json: dict[str, Any],
    ingresos_json: dict[str, Any] | None,
) -> ResultadoMotor:
    solicitud = Solicitud.model_validate(solicitud_json)
    hdc = HDCParser().parse(hdc_json)
    vi = IncomeParser().parse(ingresos_json) if ingresos_json is not None else None
    return EvaluacionService(db=None).evaluar_con_reportes(solicitud, hdc, vi)


def _solicitud_interactiva(
    hdc_json: dict[str, Any], ingresos_json: dict[str, Any] | None, destino: Path
) -> dict[str, Any]:
    hdc = hdc_json.get("ReportHDCplus", hdc_json)
    identificacion = hdc.get("identifyingAttributes", {}).get("personId", {}) or hdc.get("basicInformation", {}).get(
        "personId", {}
    )
    basic = hdc.get("basicInformation", {})
    tipo_id = identificacion.get("personIdType")
    numero_id = identificacion.get("personIdNumber")
    apellido = basic.get("firstLastName") or hdc.get("identifyingAttributes", {}).get("personLastName")

    ocupacion_default, ingreso_default = "", ""
    if ingresos_json:
        descripciones = " ".join(
            str(a.get("descripcion_cotizante_persona_natural", "")) for a in ingresos_json.get("aportantes", [])
        ).lower()
        if "independiente" in descripciones:
            ocupacion_default = "Independiente"
        elif "dependiente" in descripciones or "empleado" in descripciones:
            ocupacion_default = "Empleado"
        resumen = ingresos_json.get("resumen_general_ingresos") or {}
        ingreso_default = resumen.get("promedio_ingresos_cotizante") or ""
        vi_id = ingresos_json.get("numero_identificacion_persona_natural")
        if numero_id and vi_id and str(numero_id) != str(vi_id):
            raise ValueError("El HDC y el Valor Ingreso no corresponden a la misma identificación.")
    if not tipo_id or not numero_id or not apellido:
        raise ValueError("No se pudo obtener tipo, número de identificación y apellido desde el HDC.")

    print("No se encontró el archivo de solicitud. Completa los datos faltantes para crearlo.")
    fecha_nacimiento = input("Fecha de nacimiento (AAAA-MM-DD): ").strip()
    date.fromisoformat(fecha_nacimiento)
    ocupacion = (
        input(f"Ocupación [Empleado/Independiente/Pensionado/Fuerzas Militares] ({ocupacion_default}): ").strip()
        or ocupacion_default
    )
    contrato = input("Tipo de contrato [Indefinido/Fijo/Obra o Labor/NA] (Enter si no aplica): ").strip()
    camara = input("Años en Cámara de Comercio (solo independientes; Enter si no aplica): ").strip()
    ingreso = input(f"Ingreso mensual declarado ({ingreso_default}): ").strip() or str(ingreso_default or "0")
    otros = input("Otros ingresos mensuales [0]: ").strip() or "0"
    saldo = input("Saldo a financiar (pesos): ").strip()
    plazo = input("Plazo en meses: ").strip()
    tasa = input("Tasa mensual (%): ").strip()
    if not saldo or not plazo or not tasa:
        raise ValueError("Saldo a financiar, plazo y tasa son obligatorios.")

    datos: dict[str, Any] = {
        "tipo_id": str(tipo_id),
        "numero_id": str(numero_id),
        "primer_apellido": str(apellido),
        "ocupacion": ocupacion,
        "fecha_nacimiento": fecha_nacimiento,
        "ingresos_mensuales": ingreso,
        "otros_ingresos": otros,
        "saldo_financiar": saldo,
        "plazo": plazo,
        "tasa": tasa,
    }
    if contrato:
        datos["tipo_contrato"] = contrato
    if camara:
        datos["anios_camara_comercio"] = camara
    solicitud = Solicitud.model_validate(datos).model_dump(mode="json", exclude_none=True)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(solicitud, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Solicitud guardada en: {destino}")
    return solicitud


def _dinero(valor: Any) -> str:
    try:
        return f"${float(valor):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return "No disponible"


def _imprimir_resumen(r: ResultadoMotor) -> None:
    print("\n=== RESULTADO DEL MOTOR ===")
    print(f"Decisión: {r.decision.value}  (interna: {r.decision_interna.value})")
    print("Causales: " + ("; ".join(f"{c.codigo} {c.value}" for c in r.causales) or "Ninguna"))
    score = r.score_consultado if r.score_consultado is not None else "No disponible"
    print(f"Score: {score} (modelo {r.score_tipo or '-'})")
    perfil_score = r.perfil_score.value if r.perfil_score else "-"
    perfil_ingreso = r.perfil_ingreso.value if r.perfil_ingreso else "-"
    print(f"Perfil score: {perfil_score} | Perfil ingreso: {perfil_ingreso}")
    print(f"Ingreso final: {_dinero(r.ingreso_final)} ({r.ingreso_final_smmlv} SMMLV, fuente {r.fuente_ingreso_final})")
    print(f"Endeudamiento: {r.endeudamiento}%")
    print(f"Disponible: {_dinero(r.disponible)} | Capacidad de pago: {_dinero(r.capacidad_pago)}")
    print(f"Cupo sugerido: {_dinero(r.cupo_sugerido)} | Cuota moto: {_dinero(r.cuota_moto)}")
    for a in r.advertencias:
        print(f"Advertencia: {a}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Motor de decisión con reportes de Experian locales.")
    parser.add_argument("--solicitud", type=Path, default=Path("solicitud.json"))
    parser.add_argument("--hdc", required=True, type=Path, help="JSON o PDF de Historia de Crédito+")
    parser.add_argument("--ingresos", type=Path, help="JSON o PDF de Valor Ingreso (opcional)")
    parser.add_argument("--salida", type=Path, help="Guarda el resultado completo en JSON")
    parser.add_argument("--imprimir-json", action="store_true")
    args = parser.parse_args()

    try:
        hdc_json = leer_reporte(args.hdc)
        ingresos_json = leer_reporte(args.ingresos) if args.ingresos else None
        solicitud_json = (
            leer_reporte(args.solicitud)
            if args.solicitud.exists()
            else _solicitud_interactiva(hdc_json, ingresos_json, args.solicitud)
        )
        resultado = evaluar(solicitud_json, hdc_json, ingresos_json)
    except (ValueError, ValidationError, MotorError) as exc:
        print(f"Error de entrada: {exc}", file=sys.stderr)
        return 2

    texto = resultado.model_dump_json(indent=2)
    if args.salida:
        args.salida.write_text(texto + "\n", encoding="utf-8")
    _imprimir_resumen(resultado)
    if args.salida:
        print(f"\nDetalle completo guardado en: {args.salida}")
    if args.imprimir_json:
        print(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
