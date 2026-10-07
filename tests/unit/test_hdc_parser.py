"""Tests del parser de HDC+."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from backend.integrations.datacredito.parsers.hdc_parser import HDCparser

FIXTURE = Path(__file__).parent.parent / "integration" / "fixtures" / "hdc_response_example.json"


@pytest.fixture
def payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_parse_respuesta_basica(payload):
    parser = HDCparser()
    r = parser.parse(payload)

    assert r.respuesta_codigo == "13"
    assert r.respuesta_desc == "La consulta fue efectiva"


def test_parse_persona(payload):
    parser = HDCparser()
    r = parser.parse(payload)

    assert r.persona is not None
    assert r.persona.nombres == "NOMBRE FICTICIO"
    assert r.persona.primer_apellido == "APELLIDOUNO"
    assert r.persona.segundo_apellido == "APELLIDODOS"
    assert r.persona.edad_min == 66


def test_parse_scores(payload):
    parser = HDCparser()
    r = parser.parse(payload)

    assert len(r.scores) == 1
    assert r.scores[0].tipo == "67"
    assert r.scores[0].puntaje == 700


def test_parse_quanto(payload):
    parser = HDCparser()
    r = parser.parse(payload)

    assert r.quanto is not None
    assert r.quanto.producto == "62"
    assert r.quanto.valor_medio == 2816
    assert r.quanto.valor_medio_smlv == Decimal("4.7783")


def test_parse_cuenta_cartera(payload):
    parser = HDCparser()
    r = parser.parse(payload)

    assert len(r.cuentas_cartera) == 1
    c = r.cuentas_cartera[0]
    assert c.entidad == "BANCO FICTICIO"
    assert c.saldo_actual == 10531000
    assert c.calificacion == "A"
    assert c.calificacion_desc is None


def test_parse_rating_desc_obligacion(payload):
    payload["ReportHDCplus"]["liabilities"][0]["values"][0]["ratingDesc"] = "CALIFICACIÓN E"
    r = HDCparser().parse(payload)
    assert r.cuentas_cartera[0].calificacion_desc == "CALIFICACIÓN E"


def test_rating_actual_de_cuenta_tiene_prioridad_y_se_traduce(payload):
    cuenta = payload["ReportHDCplus"]["liabilities"][0]
    cuenta["account"]["rating"] = 5
    cuenta["account"]["ratingDesc"] = "E"
    cuenta["values"][0]["rating"] = "-"
    cuenta["values"][0]["ratingDesc"] = "NO REPORTA INFORMACIÓN"
    r = HDCparser().parse(payload)
    assert r.cuentas_cartera[0].calificacion == "E"
    assert r.cuentas_cartera[0].calificacion_desc == "E"


def test_parse_endeudamiento(payload):
    parser = HDCparser()
    r = parser.parse(payload)

    assert len(r.endeudamiento_global) == 1
    e = r.endeudamiento_global[0]
    assert e.entidad == "BANCO FICTICIO"
    assert e.saldo_pendiente == 10793000
    assert e.tipo_credito == "CNS"


def test_respuesta_vacia():
    parser = HDCparser()
    r = parser.parse({"ReportHDCplus": {}})
    assert r.persona is None
    assert r.scores == []
    assert r.quanto is None
