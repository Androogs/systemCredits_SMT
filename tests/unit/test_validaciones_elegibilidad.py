"""Validación de identidad, advertencias y motor de elegibilidad."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.models.buro_models import PersonaBasica, RespuestaValorIngreso
from backend.services.elegibilidad_service import EligibilidadService
from backend.services.motor_exceptions import IdentidadNoCoincideError
from backend.services.validaciones_identidad import (
    advertencias_consistencia,
    normalizar_identificacion,
    validar_identidad,
)


def test_normalizar_identificacion():
    assert normalizar_identificacion("0079.995.359") == "79995359"
    assert normalizar_identificacion(79995359) == "79995359"


def test_identidad_ok(solicitud_empleado, hdc_basico):
    validar_identidad(solicitud_empleado, hdc_basico, RespuestaValorIngreso(numero_id="0079995359"))


@pytest.mark.parametrize(
    "persona", [None, PersonaBasica(numero_id="111"), PersonaBasica(numero_id="79995359", tipo_id="4")]
)
def test_identidad_no_coincide_hdc(solicitud_empleado, hdc_basico, persona):
    hdc_basico.persona = persona
    with pytest.raises(IdentidadNoCoincideError):
        validar_identidad(solicitud_empleado, hdc_basico, None)


def test_identidad_no_coincide_valor_ingreso(solicitud_empleado, hdc_basico):
    with pytest.raises(IdentidadNoCoincideError):
        validar_identidad(solicitud_empleado, hdc_basico, RespuestaValorIngreso(numero_id="222"))


def test_advertencias(solicitud_empleado, hdc_basico):
    hdc_basico.persona.edad_min, hdc_basico.persona.edad_max = 20, 25
    adv = advertencias_consistencia(solicitud_empleado, hdc_basico, RespuestaValorIngreso(), date(2026, 9, 30))
    assert len(adv) == 3
    assert "Edad calculada" in adv[0] and "R13" in adv[0]


def _producto(reglas, score_min=None):
    return SimpleNamespace(
        id_aliado_producto=7,
        score_min=score_min,
        reglas=[SimpleNamespace(campo=c, operador=o, valor_json=v) for c, o, v in reglas],
    )


def test_elegibilidad_cumple_y_no_cumple():
    datos = {"score": Decimal("720"), "ingreso_final_smmlv": Decimal("2.1"), "ocupacion": "Empleado"}
    servicio = EligibilidadService()
    ok = servicio.evaluar_producto("id", _producto([("score", ">=", 700), ("ocupacion", "IN", ["Empleado"])]), datos)
    assert ok.elegible and ok.motivo_no_elegible is None
    no = servicio.evaluar_producto("id", _producto([("ingreso_final_smmlv", ">=", 3)], score_min=750), datos)
    assert (
        not no.elegible and "ingreso_final_smmlv" in no.motivo_no_elegible and "score >= 750" in no.motivo_no_elegible
    )


def test_elegibilidad_campo_ausente_no_cumple():
    r = EligibilidadService().evaluar_producto("id", _producto([("campo_raro", ">=", 1)]), {})
    assert not r.elegible


def test_elegibilidad_operador_invalido():
    with pytest.raises(ValueError):
        EligibilidadService().evaluar_producto("id", _producto([("score", "~", 1)]), {"score": 1})
