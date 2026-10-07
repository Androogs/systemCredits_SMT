"""Tests de politicas de rechazo (BRD 2.4.1).

Cubre las 12 politicas evaluadas en `app/domain/rules/rechazo.py`:

  R2  - Embargos cuentas corrientes / ahorro
  R3  - Cancelaciones negativas (evento buro 03) ultimos 12 meses
  R4  - Cartera castigada (estado_pago 45 o 'C' en vector)
  R5  - Dudoso recaudo (estado_pago 47 o 'D' en vector)
  R6  - Mora 60+ vigente
  R7  - Moras 30d historicas (ult 12 meses) >= 4
  R8  - Moras 60d historicas (ult 12 meses) >= 2
  R9  - Moras 90d historicas (ult 12 meses) >= 1
  R10 - Calificacion C/D/E/K
  R11 - Reestructuradas >= 2 en ultimo ano
  R12 - Documento no vigente
  R13 - Edad fuera de rango

Casos de borde que validan los fixes aplicados:
  - Vector con D/C fuera de los ultimos 12 meses no dispara R4/R5
  - Estado pago '03' (Pago Total) no debe contar como castigada / mora
  - Telcos con saldo_mora <= saldo_mora_be no disparan reglas con Telcos
  - Codeudores y cuentas bloqueadas no cuentan
  - Reglas con "incluye_telcos=False" (R3 y R11) excluyen Telcos aun
    con saldo_mora alto; R10 aplica en todos los sectores
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend.models.enums import (
    Causal,
    EconomicSector,
    Ocupacion,
    TipoContrato,
    TipoIdentificacion,
)
from backend.services.reglas_filtros_duros import evaluar_filtros_duros as evaluar_rechazo
from tests.modelos import (
    CuentaAhorro,
    CuentaCartera,
    CuentaCorriente,
    PersonaBasica,
    RespuestaHDC,
    Solicitud,
    TarjetaCredito,
)

# ---------------------------------------------------------------------------
# Constantes de prueba
# ---------------------------------------------------------------------------
FECHA_EVAL = date(2025, 6, 15)
VECTOR_LIMPIO = "N" * 47  # 47 meses al dia
VECTOR_12M = "N" * 12


# ---------------------------------------------------------------------------
# Helpers de construccion
# ---------------------------------------------------------------------------
def _cuenta_cartera(**overrides) -> CuentaCartera:
    defaults = dict(
        entidad="BANCO X",
        numero="123456",
        tipo_cuenta="CAB",
        calificacion="A",
        estado_pago="01",
        saldo_actual=Decimal("1000000"),
        saldo_mora=Decimal("0"),
        cuota=Decimal("100000"),
        comportamiento=VECTOR_LIMPIO,
        sector="1",  # Financiero
        bloqueada=False,
        calidad_deudor="00",
        forma_pago="Mensual",
    )
    defaults.update(overrides)
    return CuentaCartera(**defaults)


def _tarjeta(**overrides) -> TarjetaCredito:
    defaults = dict(
        entidad="BANCO Y",
        numero="654321",
        calificacion="A",
        estado_pago="01",
        saldo_actual=Decimal("500000"),
        saldo_mora=Decimal("0"),
        cuota=Decimal("50000"),
        comportamiento=VECTOR_LIMPIO,
        sector="1",
        bloqueada=False,
        calidad_deudor="00",
        forma_pago="Mensual",
    )
    defaults.update(overrides)
    return TarjetaCredito(**defaults)


def _cuenta_ahorro(**overrides) -> CuentaAhorro:
    defaults = dict(
        entidad="BANCO Z",
        numero="111",
        estado="01",  # activa (no embargada)
        bloqueada=False,
    )
    defaults.update(overrides)
    return CuentaAhorro(**defaults)


def _cuenta_corriente(**overrides) -> CuentaCorriente:
    defaults = dict(
        entidad="BANCO W",
        numero="222",
        estado="01",
        bloqueada=False,
    )
    defaults.update(overrides)
    return CuentaCorriente(**defaults)


def _hdc(**overrides) -> RespuestaHDC:
    defaults = dict(
        persona=PersonaBasica(
            nombres="TEST",
            primer_apellido="TEST",
            numero_id="12345678",
            estado_documento="00",
        ),
        cuentas_cartera=[],
        tarjetas_credito=[],
        cuentas_ahorro=[],
        cuentas_corriente=[],
    )
    defaults.update(overrides)
    return RespuestaHDC(**defaults)


def _solicitud(**overrides) -> Solicitud:
    defaults = dict(
        tipo_id=TipoIdentificacion.CC,
        numero_id="12345678",
        primer_apellido="TEST",
        ocupacion=Ocupacion.EMPLEADO,
        tipo_contrato=TipoContrato.INDEFINIDO,
        antiguedad_meses=36,
        fecha_nacimiento=date(1985, 1, 1),  # ~40 anios
    )
    defaults.update(overrides)
    return Solicitud(**defaults)


def _causales(resultado) -> set[Causal]:
    return set(resultado.lista_causales)


# ---------------------------------------------------------------------------
# R2 - Embargos cuentas corrientes / ahorro
# ---------------------------------------------------------------------------
class TestR2Embargos:
    def test_cuenta_ahorro_embargada_dispara(self, parametros_demo):
        hdc = _hdc(cuentas_ahorro=[_cuenta_ahorro(estado="06")])
        r = evaluar_rechazo(hdc, _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R2 in _causales(r)

    def test_cuenta_corriente_embargada_activa_dispara(self, parametros_demo):
        # Estado 07 = Embargada-Activa
        hdc = _hdc(cuentas_corriente=[_cuenta_corriente(estado="07")])
        r = evaluar_rechazo(hdc, _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R2 in _causales(r)

    def test_cuenta_activa_no_dispara(self, parametros_demo):
        hdc = _hdc(cuentas_ahorro=[_cuenta_ahorro(estado="01")])
        r = evaluar_rechazo(hdc, _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R2 not in _causales(r)

    def test_sin_cuentas_no_dispara(self, parametros_demo):
        r = evaluar_rechazo(_hdc(), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R2 not in _causales(r)


# ---------------------------------------------------------------------------
# R3 - Cancelaciones negativas (evento_buro 03 en ultimo ano)
# ---------------------------------------------------------------------------
class TestR3Cancelaciones:
    def test_cancelacion_reciente_dispara(self, parametros_demo):
        tdc = _tarjeta(
            evento_buro="03",
            fecha_evento=FECHA_EVAL - timedelta(days=90),
        )
        r = evaluar_rechazo(_hdc(tarjetas_credito=[tdc]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R3 in _causales(r)

    def test_cancelacion_reciente_codigo_sin_cero_dispara(self, parametros_demo):
        tdc = _tarjeta(
            evento_buro="3",
            fecha_evento=FECHA_EVAL - timedelta(days=90),
        )
        r = evaluar_rechazo(_hdc(tarjetas_credito=[tdc]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R3 in _causales(r)

    def test_ventana_se_ancla_a_fecha_actualizacion(self, parametros_demo):
        tdc = _tarjeta(
            evento_buro="03",
            fecha_evento=date(2024, 4, 1),
            fecha_actualizacion=date(2025, 3, 1),
        )
        r = evaluar_rechazo(_hdc(tarjetas_credito=[tdc]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R3 in _causales(r)

    def test_cancelacion_vieja_no_dispara(self, parametros_demo):
        tdc = _tarjeta(
            evento_buro="03",
            fecha_evento=FECHA_EVAL - timedelta(days=400),  # > 1 anio
        )
        r = evaluar_rechazo(_hdc(tarjetas_credito=[tdc]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R3 not in _causales(r)

    def test_otro_evento_no_dispara(self, parametros_demo):
        tdc = _tarjeta(
            evento_buro="08",  # Pago voluntario, no cancelacion
            fecha_evento=FECHA_EVAL - timedelta(days=30),
        )
        r = evaluar_rechazo(_hdc(tarjetas_credito=[tdc]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R3 not in _causales(r)

    def test_sin_fecha_no_dispara(self, parametros_demo):
        tdc = _tarjeta(evento_buro="03", fecha_evento=None)
        r = evaluar_rechazo(_hdc(tarjetas_credito=[tdc]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R3 not in _causales(r)

    def test_telcos_no_dispara_aunque_evento_03(self, parametros_demo):
        # R3 usa incluye_telcos=False → Telcos nunca dispara aunque saldo_mora alto
        tdc = _tarjeta(
            sector=EconomicSector.TELCOS.value,
            saldo_mora=Decimal("999999999"),
            evento_buro="03",
            fecha_evento=FECHA_EVAL - timedelta(days=30),
        )
        r = evaluar_rechazo(_hdc(tarjetas_credito=[tdc]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R3 not in _causales(r)


# ---------------------------------------------------------------------------
# R4 - Cartera castigada (estado_pago 45 o 'C' en vector 12m)
# ---------------------------------------------------------------------------
class TestR4CarteraCastigada:
    def test_estado_45_dispara(self, parametros_demo):
        c = _cuenta_cartera(estado_pago="45")
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R4 in _causales(r)

    def test_vector_c_dispara(self, parametros_demo):
        # 'C' en el mes 1 (mas reciente)
        c = _cuenta_cartera(comportamiento="C" + "N" * 46)
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R4 in _causales(r)

    def test_vector_c_fuera_de_12m_no_dispara(self, parametros_demo):
        """Bug fix: 'C' en el mes 30 (fuera de ventana) NO debe contar."""
        # 'C' en la posicion 30 → no está en [:12]
        vector = "N" * 30 + "C" + "N" * 16
        c = _cuenta_cartera(comportamiento=vector)
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R4 not in _causales(r), "El vector debe evaluarse solo en los ultimos 12 meses"

    def test_calificacion_c_sola_no_dispara_r4(self, parametros_demo):
        """Calificacion C dispara R10, NO R4. R4 es por estado o vector."""
        c = _cuenta_cartera(calificacion="C", estado_pago="01", comportamiento=VECTOR_LIMPIO)
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R4 not in _causales(r)
        assert Causal.R10 in _causales(r)


# ---------------------------------------------------------------------------
# R5 - Dudoso recaudo (estado_pago 47 o 'D' en vector 12m)
# ---------------------------------------------------------------------------
class TestR5DudosoRecaudo:
    def test_estado_47_dispara(self, parametros_demo):
        c = _cuenta_cartera(estado_pago="47")
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R5 in _causales(r)

    def test_vector_d_dispara(self, parametros_demo):
        c = _cuenta_cartera(comportamiento="D" + "N" * 46)
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R5 in _causales(r)

    def test_dos_obligaciones_dudoso_recaudo_cuentan_dos(self, parametros_demo):
        cuentas = [
            _cuenta_cartera(numero="000000001", estado_pago="47", estado_cuenta_desc="Dudoso recaudo"),
            _cuenta_cartera(numero="000000002", estado_pago="47", estado_cuenta_desc="Dudoso recaudo"),
        ]
        r = evaluar_rechazo(_hdc(cuentas_cartera=cuentas), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R5 in _causales(r)
        assert r.indicadores.dudoso_recaudo == 2

    def test_descripcion_dudoso_recaudo_dispara_si_falta_codigo(self, parametros_demo):
        c = _cuenta_cartera(estado_pago="", estado_cuenta_desc="Dudoso recaudo")
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R5 in _causales(r)

    def test_vector_d_fuera_de_12m_no_dispara(self, parametros_demo):
        """Bug fix: 'D' fuera de los ultimos 12 meses NO debe contar."""
        vector = "N" * 30 + "D" + "N" * 16
        c = _cuenta_cartera(comportamiento=vector)
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R5 not in _causales(r)


# ---------------------------------------------------------------------------
# R6 - Mora 60+ vigente
# ---------------------------------------------------------------------------
class TestR6Mora60Vigente:
    def test_mora_60_dispara(self, parametros_demo):
        # '2' = mora 60 dias, en el mes mas reciente
        c = _cuenta_cartera(comportamiento="2" + "N" * 46, estado_pago="18")
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R6 in _causales(r)

    def test_mora_90_tambien_dispara(self, parametros_demo):
        c = _cuenta_cartera(comportamiento="3" + "N" * 46, estado_pago="19")
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R6 in _causales(r)

    def test_telcos_con_saldo_superior_al_umbral_cuenta_en_r6(self, parametros_demo):
        c = _cuenta_cartera(
            comportamiento="2" + "N" * 46,
            sector="Telcos",
            saldo_mora=parametros_demo.saldo_mora_be + 1,
        )
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert r.indicadores.mora_60_vigente == 1
        assert Causal.R6 in _causales(r)

    def test_mora_30_sola_no_dispara_r6(self, parametros_demo):
        c = _cuenta_cartera(comportamiento="1" + "N" * 46, estado_pago="17")
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R6 not in _causales(r)

    def test_estado_pago_03_no_dispara_r6(self, parametros_demo):
        """Pago total (03) esta cerrada, no debe contar como mora vigente."""
        c = _cuenta_cartera(
            comportamiento="2" + "N" * 46,
            estado_pago="03",
        )
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R6 not in _causales(r)

    def test_bloqueada_no_dispara_r6(self, parametros_demo):
        c = _cuenta_cartera(
            comportamiento="2" + "N" * 46,
            bloqueada=True,
        )
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R6 not in _causales(r)


# ---------------------------------------------------------------------------
# R7 - Moras 30d historicas (12m) >= 2
# ---------------------------------------------------------------------------
class TestR7MoraHistorica30:
    def test_dos_moras_30_dispara(self, parametros_demo):
        c = _cuenta_cartera(comportamiento="11" + "N" * 45)
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R7 in _causales(r)

    def test_tres_moras_30_tambien_dispara(self, parametros_demo):
        c = _cuenta_cartera(comportamiento="111" + "N" * 44)
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R7 in _causales(r)

    def test_una_mora_30_no_dispara(self, parametros_demo):
        c = _cuenta_cartera(comportamiento="1" + "N" * 46)
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R7 not in _causales(r)

    def test_codeudor_no_cuenta(self, parametros_demo):
        c = _cuenta_cartera(
            comportamiento="11" + "N" * 45,
            calidad_deudor="01",
        )
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R7 not in _causales(r)

    def test_texto_codeudor_no_cuenta(self, parametros_demo):
        c = _cuenta_cartera(
            comportamiento="11" + "N" * 45,
            calidad_deudor="CODEUDOR SOLIDARIO",
        )
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R7 not in _causales(r)


# ---------------------------------------------------------------------------
# R8 - Moras 60d historicas (12m) >= 1
# ---------------------------------------------------------------------------
class TestR8MoraHistorica60:
    def test_una_mora_60_dispara(self, parametros_demo):
        c = _cuenta_cartera(comportamiento="2" + "N" * 46)
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R8 in _causales(r)

    def test_dos_moras_60_tambien_dispara(self, parametros_demo):
        c = _cuenta_cartera(comportamiento="22" + "N" * 45)
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R8 in _causales(r)

    def test_sin_moras_60_no_dispara(self, parametros_demo):
        c = _cuenta_cartera(comportamiento="11" + "N" * 45)  # solo moras 30d
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R8 not in _causales(r)

    def test_mora_90_no_cuenta_para_r8(self, parametros_demo):
        """R8 cuenta únicamente el nivel 2; los niveles 3-6 pertenecen a R9."""
        c = _cuenta_cartera(comportamiento="3" + "N" * 46)
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R8 not in _causales(r)
        assert Causal.R9 in _causales(r)

    def test_conteos_por_banda_y_vigencia_con_telcos_bajo_umbral(self, parametros_demo):
        vectores = [
            "21111NNNNNNN",
            "24321NNNNNNN",
            "NN21NNNNNNNN",
            "34321NNNNNNN",
            "24321NNNNNNN",
            "4321NN",
            "D4321NNNNNNN",
            "21NNNNNN",
        ]
        cuentas = [_cuenta_cartera(comportamiento=vector) for vector in vectores[:-1]]
        cuentas.append(
            _cuenta_cartera(
                comportamiento=vectores[-1],
                sector=EconomicSector.TELCOS.value,
                saldo_mora=Decimal("60000"),
            )
        )
        r = evaluar_rechazo(_hdc(cuentas_cartera=cuentas), _solicitud(), parametros_demo, FECHA_EVAL)
        assert r.indicadores.mora_60_vigente == 5
        assert r.indicadores.moras_30_historicas == 10
        assert r.indicadores.moras_60_historicas == 9
        assert r.indicadores.moras_90_historicas == 11
        assert r.indicadores.mora_30_vigente == 0
        assert Causal.E2 not in _causales(r)


# ---------------------------------------------------------------------------
# R9 - Moras 90d historicas (12m) >= 1
# ---------------------------------------------------------------------------
class TestR9MoraHistorica90:
    def test_una_mora_90_dispara(self, parametros_demo):
        c = _cuenta_cartera(comportamiento="3" + "N" * 46)
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R9 in _causales(r)

    def test_sin_moras_90_no_dispara(self, parametros_demo):
        c = _cuenta_cartera(comportamiento="22" + "N" * 45)
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R9 not in _causales(r)


# ---------------------------------------------------------------------------
# R10 - Calificacion C, D, E, K
# ---------------------------------------------------------------------------
class TestR10CalificacionNegativa:
    @pytest.mark.parametrize("calif", ["C", "D", "E", "K"])
    def test_calificacion_negativa_dispara(self, calif, parametros_demo):
        c = _cuenta_cartera(calificacion=calif)
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R10 in _causales(r)

    @pytest.mark.parametrize("calif", ["A", "AA", "B", "BB", "CC"])
    def test_calificacion_positiva_no_dispara(self, calif, parametros_demo):
        c = _cuenta_cartera(calificacion=calif)
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R10 not in _causales(r)

    def test_codeudor_no_cuenta(self, parametros_demo):
        c = _cuenta_cartera(calificacion="E", calidad_deudor="01")
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R10 not in _causales(r)

    def test_telcos_dispara_con_calificacion_e(self, parametros_demo):
        """R10 aplica en todos los sectores, incluido Telcos."""
        c = _cuenta_cartera(
            sector=EconomicSector.TELCOS.value,
            saldo_mora=Decimal("0"),
            calificacion="E",
        )
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R10 in _causales(r)

    def test_cuatro_calificaciones_negativas_incluyendo_telcos(self, parametros_demo):
        cuentas = [
            _cuenta_cartera(calificacion="K"),
            _cuenta_cartera(calificacion="E", sector=EconomicSector.TELCOS.value),
            _cuenta_cartera(calificacion="E"),
            _cuenta_cartera(calificacion="D"),
        ]
        r = evaluar_rechazo(_hdc(cuentas_cartera=cuentas), _solicitud(), parametros_demo, FECHA_EVAL)
        assert r.indicadores.calificaciones_negativas == 4
        assert Causal.R10 in _causales(r)

    def test_sin_calificacion_no_dispara(self, parametros_demo):
        c = _cuenta_cartera(calificacion=None)
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R10 not in _causales(r)


# ---------------------------------------------------------------------------
# R11 - Reestructuradas / refinanciadas >= 2 en el ultimo anio
# ---------------------------------------------------------------------------
class TestR11Reestructuracion:
    def test_dos_reestructuradas_recientes_dispara(self, parametros_demo):
        c1 = _cuenta_cartera(
            estado_origen_desc="REESTRUCTURADA",
            fecha_estado_origen=FECHA_EVAL - timedelta(days=90),
        )
        c2 = _cuenta_cartera(
            estado_origen_desc="REFINANCIADA",
            fecha_estado_origen=FECHA_EVAL - timedelta(days=180),
        )
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c1, c2]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R11 in _causales(r)

    def test_una_reestructurada_no_dispara(self, parametros_demo):
        c = _cuenta_cartera(
            estado_origen_desc="REESTRUCTURADA",
            fecha_estado_origen=FECHA_EVAL - timedelta(days=90),
        )
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R11 not in _causales(r)

    def test_reestructurada_vieja_no_dispara(self, parametros_demo):
        c1 = _cuenta_cartera(
            estado_origen_desc="REESTRUCTURADA",
            fecha_estado_origen=FECHA_EVAL - timedelta(days=500),
        )
        c2 = _cuenta_cartera(
            estado_origen_desc="REFINANCIADA",
            fecha_estado_origen=FECHA_EVAL - timedelta(days=600),
        )
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c1, c2]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R11 not in _causales(r)

    def test_sin_fecha_origen_no_dispara(self, parametros_demo):
        c1 = _cuenta_cartera(estado_origen_desc="REESTRUCTURADA", fecha_estado_origen=None)
        c2 = _cuenta_cartera(estado_origen_desc="REESTRUCTURADA", fecha_estado_origen=None)
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c1, c2]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R11 not in _causales(r)

    def test_renegociacion_tambien_cuenta(self, parametros_demo):
        c1 = _cuenta_cartera(
            estado_origen_desc="RENEGOCIACION",
            fecha_estado_origen=FECHA_EVAL - timedelta(days=90),
        )
        c2 = _cuenta_cartera(
            estado_origen_desc="REESTRUCTURADA",
            fecha_estado_origen=FECHA_EVAL - timedelta(days=180),
        )
        r = evaluar_rechazo(_hdc(cuentas_cartera=[c1, c2]), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R11 in _causales(r)


# ---------------------------------------------------------------------------
# R12 - Estado documento no vigente
# ---------------------------------------------------------------------------
class TestR12Documento:
    def test_documento_cancelado_dispara(self, parametros_demo):
        hdc = _hdc(persona=PersonaBasica(estado_documento="21", numero_id="123"))
        r = evaluar_rechazo(hdc, _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R12 in _causales(r)

    def test_documento_vigente_00_no_dispara(self, parametros_demo):
        hdc = _hdc(persona=PersonaBasica(estado_documento="00", numero_id="123"))
        r = evaluar_rechazo(hdc, _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R12 not in _causales(r)

    def test_documento_25_no_dispara(self, parametros_demo):
        """Estado 25 = Cedula de extranjeria, se considera valido."""
        hdc = _hdc(persona=PersonaBasica(estado_documento="25", numero_id="123"))
        r = evaluar_rechazo(hdc, _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R12 not in _causales(r)

    def test_documento_en_tramite_88_dispara(self, parametros_demo):
        hdc = _hdc(persona=PersonaBasica(estado_documento="88", numero_id="123"))
        r = evaluar_rechazo(hdc, _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R12 in _causales(r)

    def test_sin_persona_no_dispara(self, parametros_demo):
        r = evaluar_rechazo(_hdc(persona=None), _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R12 not in _causales(r)

    def test_sin_estado_documento_no_dispara(self, parametros_demo):
        hdc = _hdc(persona=PersonaBasica(estado_documento=None, numero_id="123"))
        r = evaluar_rechazo(hdc, _solicitud(), parametros_demo, FECHA_EVAL)
        assert Causal.R12 not in _causales(r)


# ---------------------------------------------------------------------------
# R13 - Edad fuera de rango
# ---------------------------------------------------------------------------
class TestR13Edad:
    def test_menor_que_minima_dispara(self, parametros_demo):
        # parametros_demo.edad_minima_be = 18
        solicitud = _solicitud(fecha_nacimiento=date(FECHA_EVAL.year - 17, FECHA_EVAL.month, FECHA_EVAL.day))
        r = evaluar_rechazo(_hdc(), solicitud, parametros_demo, FECHA_EVAL)
        assert Causal.R13 in _causales(r)

    def test_mayor_o_igual_que_maxima_dispara(self, parametros_demo):
        # parametros_demo.edad_maxima_be = 75
        solicitud = _solicitud(fecha_nacimiento=date(FECHA_EVAL.year - 75, FECHA_EVAL.month, FECHA_EVAL.day))
        r = evaluar_rechazo(_hdc(), solicitud, parametros_demo, FECHA_EVAL)
        assert Causal.R13 in _causales(r)

    def test_edad_dentro_de_rango_no_dispara(self, parametros_demo):
        solicitud = _solicitud(fecha_nacimiento=date(FECHA_EVAL.year - 40, FECHA_EVAL.month, FECHA_EVAL.day))
        r = evaluar_rechazo(_hdc(), solicitud, parametros_demo, FECHA_EVAL)
        assert Causal.R13 not in _causales(r)

    def test_exactamente_en_el_minimo_no_dispara(self, parametros_demo):
        # edad == 18 no debe rechazar
        solicitud = _solicitud(fecha_nacimiento=date(FECHA_EVAL.year - 18, FECHA_EVAL.month, FECHA_EVAL.day))
        r = evaluar_rechazo(_hdc(), solicitud, parametros_demo, FECHA_EVAL)
        assert Causal.R13 not in _causales(r)


# ---------------------------------------------------------------------------
# Multiples causales simultaneas (flujo LINEAL)
# ---------------------------------------------------------------------------
class TestMultiplesCausales:
    def test_flujo_lineal_acumula_causales(self, parametros_demo):
        """El BRD exige flujo LINEAL: se recopilan todas las causales."""
        c = _cuenta_cartera(
            calificacion="E",  # R10
            estado_pago="47",  # R5
            comportamiento="D" * 12 + "N" * 35,
        )
        hdc = _hdc(
            cuentas_cartera=[c],
            persona=PersonaBasica(estado_documento="21", numero_id="123"),  # R12
            cuentas_ahorro=[_cuenta_ahorro(estado="06")],  # R2
        )
        r = evaluar_rechazo(hdc, _solicitud(), parametros_demo, FECHA_EVAL)
        causales = _causales(r)
        assert Causal.R2 in causales
        assert Causal.R5 in causales
        assert Causal.R10 in causales
        assert Causal.R12 in causales

    def test_hdc_limpio_no_dispara_ninguna(self, parametros_demo):
        """Caso control: HDC sin problemas no debe producir rechazos."""
        hdc = _hdc(
            persona=PersonaBasica(estado_documento="00", numero_id="123"),
            cuentas_cartera=[_cuenta_cartera()],
            tarjetas_credito=[_tarjeta()],
            cuentas_ahorro=[_cuenta_ahorro(estado="01")],
        )
        r = evaluar_rechazo(hdc, _solicitud(), parametros_demo, FECHA_EVAL)
        assert not r.aplica, f"Causales inesperadas: {r.causales}"
