"""Políticas del BRD que complementan la PPT v4 y derivación de indicadores."""

from datetime import date
from decimal import Decimal

import pytest

from backend.models.buro_models import CuentaCartera, PersonaBasica, RespuestaHDC, TarjetaCredito
from backend.models.enums import Causal, Decision, TipoIdentificacion
from backend.services.reglas_filtros_duros import (
    derivar_indicadores_buro,
    evaluar_exclusion_score,
    evaluar_filtros_duros,
    evaluar_politicas_solicitud,
)

FECHA = date(2026, 9, 30)


def _causales(solicitud, params, hdc=None, exclusion=None):
    hdc = hdc or RespuestaHDC(persona=PersonaBasica(numero_id="79995359", estado_documento="00"))
    return evaluar_filtros_duros(hdc, solicitud, params, FECHA, exclusion).lista_causales


def test_solicitud_limpia_sin_causales(solicitud_empleado, parametros_demo):
    assert _causales(solicitud_empleado, parametros_demo) == []


def test_nacionalidad_diferente_rechaza(solicitud_empleado, parametros_demo):
    s = solicitud_empleado.model_copy(update={"nacionalidad": "Venezuela"})
    assert Causal.R21 in _causales(s, parametros_demo)


@pytest.mark.parametrize("valor", ["Colombia", "colombiana", "CO", " COLOMBIA "])
def test_nacionalidad_colombiana_variantes(solicitud_empleado, parametros_demo, valor):
    s = solicitud_empleado.model_copy(update={"nacionalidad": valor})
    assert Causal.R21 not in _causales(s, parametros_demo)


def test_multas_runt_rechaza(solicitud_empleado, parametros_demo):
    s = solicitud_empleado.model_copy(update={"tiene_multas_runt": True})
    assert Causal.R22 in _causales(s, parametros_demo)


@pytest.mark.parametrize("tipo", [TipoIdentificacion.NIT, TipoIdentificacion.PJE])
def test_persona_juridica(solicitud_empleado, parametros_demo, tipo):
    s = solicitud_empleado.model_copy(update={"tipo_id": tipo})
    assert Causal.E1 in _causales(s, parametros_demo)


def test_persona_juridica_puede_desactivarse(solicitud_empleado, parametros_demo):
    s = solicitud_empleado.model_copy(update={"tipo_id": TipoIdentificacion.NIT})
    p = parametros_demo.model_copy(update={"activar_exclusion_persona_juridica": False})
    assert Causal.E1 not in _causales(s, p)


def test_edad_aplica_limites_inclusivo_y_exclusivo(solicitud_empleado, parametros_demo):
    s18 = solicitud_empleado.model_copy(update={"fecha_nacimiento": date(2008, 9, 30)})
    s17 = solicitud_empleado.model_copy(update={"fecha_nacimiento": date(2008, 10, 1)})
    s65 = solicitud_empleado.model_copy(update={"fecha_nacimiento": date(1960, 10, 1)})
    s66 = solicitud_empleado.model_copy(update={"fecha_nacimiento": date(1960, 9, 30)})
    assert Causal.R13 not in [c.causal for c in evaluar_politicas_solicitud(s18, parametros_demo, FECHA)]
    assert Causal.R13 in [c.causal for c in evaluar_politicas_solicitud(s17, parametros_demo, FECHA)]
    assert Causal.R13 not in [c.causal for c in evaluar_politicas_solicitud(s65, parametros_demo, FECHA)]
    assert Causal.R13 in [c.causal for c in evaluar_politicas_solicitud(s66, parametros_demo, FECHA)]


def test_fallecido_por_score_3(solicitud_empleado, parametros_demo):
    exclusion = evaluar_exclusion_score(Decimal("3"))
    assert exclusion.fallecido and not exclusion.es_exclusion
    assert _causales(solicitud_empleado, parametros_demo, exclusion=exclusion)[0] == Causal.R1


@pytest.mark.parametrize("score,codigo", [(Decimal("0"), 0), (Decimal("4"), 4)])
def test_codigos_de_exclusion(score, codigo):
    r = evaluar_exclusion_score(score)
    assert r.es_exclusion and r.codigo_exclusion == codigo and not r.fallecido


def test_exclusion_score_0_puede_desactivarse(parametros_demo):
    p = parametros_demo.model_copy(update={"activar_exclusion_score_0": False})
    r = evaluar_exclusion_score(Decimal("0"), p)
    assert not r.es_exclusion and r.ignorada and r.codigo_exclusion == 0


def test_exclusion_fallecido_puede_desactivarse(parametros_demo):
    p = parametros_demo.model_copy(update={"activar_exclusion_score_3_fallecido": False})
    r = evaluar_exclusion_score(Decimal("3"), p)
    assert not r.es_exclusion and r.ignorada and not r.fallecido


@pytest.mark.parametrize("score", [None, Decimal("800"), Decimal("3.5"), Decimal("40")])
def test_scores_normales_no_son_exclusion(score):
    r = evaluar_exclusion_score(score)
    assert not r.es_exclusion and not r.fallecido


def test_mora_30_vigente_es_estudio_y_telcos_bajo_umbral_no_cuenta(solicitud_empleado, parametros_demo):
    normal = CuentaCartera(comportamiento="1" + "N" * 20, estado_pago="17", sector="1", calidad_deudor="00")
    telco_bajo = CuentaCartera(
        comportamiento="1" + "N" * 20, estado_pago="17", sector="4", saldo_mora=Decimal("300000"), calidad_deudor="00"
    )
    hdc1 = RespuestaHDC(persona=PersonaBasica(numero_id="1", estado_documento="00"), cuentas_cartera=[normal])
    hdc2 = RespuestaHDC(persona=PersonaBasica(numero_id="1", estado_documento="00"), cuentas_cartera=[telco_bajo])
    c1 = _causales(solicitud_empleado, parametros_demo, hdc1)
    assert c1 == [Causal.E2] and Causal.E2.tipo == Decision.RECHAZADO
    assert _causales(solicitud_empleado, parametros_demo, hdc2) == []


def test_indicadores_peor_calificacion_y_documento(parametros_demo):
    hdc = RespuestaHDC(
        persona=PersonaBasica(numero_id="1", estado_documento="25"),
        cuentas_cartera=[
            CuentaCartera(calificacion="B", calidad_deudor="00"),
            CuentaCartera(calificacion="D", calidad_deudor="00"),
            CuentaCartera(calificacion="K", calidad_deudor="01"),  # codeudor: no cuenta
        ],
    )
    ind = derivar_indicadores_buro(hdc, parametros_demo, FECHA)
    assert ind.peor_calificacion == "D"
    assert ind.calificaciones_negativas == 1
    assert ind.documento_vigente  # 25 = excepción cédula de extranjería


def test_calificacion_historica_cerrada_y_vigente_abierta(parametros_demo):
    hdc = RespuestaHDC(
        cuentas_cartera=[
            CuentaCartera(calificacion="A", comportamiento="K" + "N" * 11, estado_pago="03", calidad_deudor="00"),
            CuentaCartera(calificacion="D", comportamiento="N" * 12, estado_pago="17", calidad_deudor="00"),
            CuentaCartera(calificacion="A", comportamiento="D" + "N" * 11, estado_pago="17", calidad_deudor="00"),
        ]
    )
    ind = derivar_indicadores_buro(hdc, parametros_demo, FECHA)
    assert ind.calificaciones_negativas == 2


def test_tarjeta_cancelada_evento_05_usa_calificacion_historica(parametros_demo):
    tarjeta = TarjetaCredito(
        calificacion="A",
        comportamiento="K" + "N" * 11,
        estado_pago="00",
        estado_cuenta_desc="NO REPORTO",
        evento_buro="05",
        calidad_deudor="00",
    )
    ind = derivar_indicadores_buro(RespuestaHDC(tarjetas_credito=[tarjeta]), parametros_demo, FECHA)
    assert ind.calificaciones_negativas == 1


def test_reestructuracion_por_codigo_y_texto(parametros_demo):
    hdc = RespuestaHDC(
        cuentas_cartera=[
            CuentaCartera(estado_origen="12", fecha_estado_origen=FECHA, calidad_deudor="00"),
            CuentaCartera(estado_origen_desc="Crédito refinanciado", fecha_estado_origen=FECHA, calidad_deudor="00"),
        ]
    )
    ind = derivar_indicadores_buro(hdc, parametros_demo, FECHA)
    assert ind.reestructuraciones == 2


def test_umbral_mora_30_parametrizable(solicitud_empleado, parametros_demo):
    cuenta = CuentaCartera(comportamiento="11" + "N" * 20, calidad_deudor="00")
    hdc = RespuestaHDC(persona=PersonaBasica(numero_id="1", estado_documento="00"), cuentas_cartera=[cuenta])
    assert Causal.R7 in _causales(solicitud_empleado, parametros_demo, hdc)
    p = parametros_demo.model_copy(update={"umbral_mora_30_historica": 3})
    assert Causal.R7 not in _causales(solicitud_empleado, p, hdc)
