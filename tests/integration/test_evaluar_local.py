"""CLI de evaluación local con reportes exportados."""

import json
from pathlib import Path

import pytest

from backend.services.motor_exceptions import IdentidadNoCoincideError, ValidacionError
from backend.utils.lectura_reportes import leer_reporte_bytes
from scripts.evaluar_local import evaluar, main

FIXTURES = Path(__file__).parent / "fixtures"
SOLICITUD = {
    "tipo_id": "1",
    "numero_id": "1000000001",
    "primer_apellido": "APELLIDOUNO",
    "ocupacion": "Pensionado",
    "fecha_nacimiento": "1958-01-01",
    "ingresos_mensuales": "3000000",
    "saldo_financiar": "8000000",
    "plazo": 24,
    "tasa": "2",
}


def _json(nombre):
    return json.loads((FIXTURES / nombre).read_text(encoding="utf-8"))


def test_evaluar_con_fixture_hdc():
    r = evaluar(SOLICITUD, _json("hdc_response_example.json"), None)
    # 68 años: fuera de la política de edad (< 66)
    assert r.decision.value == "Rechazado"
    assert r.causales[0].codigo == "R13"
    assert r.score_consultado == 700


def test_evaluar_detecta_valor_ingreso_de_otra_persona():
    with pytest.raises(IdentidadNoCoincideError):
        evaluar(SOLICITUD, _json("hdc_response_example.json"), _json("income_response_example.json"))


def test_main_escribe_salida(tmp_path, monkeypatch):
    sol = tmp_path / "solicitud.json"
    sol.write_text(json.dumps(SOLICITUD))
    salida = tmp_path / "resultado.json"
    monkeypatch.setattr(
        "sys.argv",
        ["x", "--solicitud", str(sol), "--hdc", str(FIXTURES / "hdc_response_example.json"), "--salida", str(salida)],
    )
    assert main() == 0
    assert json.loads(salida.read_text())["decision"] == "Rechazado"


def test_lectura_json_invalido():
    with pytest.raises(ValidacionError):
        leer_reporte_bytes(b"{mal", "x.json")
    with pytest.raises(ValidacionError):
        leer_reporte_bytes(b"[1,2]", "x.json")
