"""Pruebas de funciones financieras y capacidad de pago (BRD 2.4.8 / PPT v4)."""

from datetime import date
from decimal import Decimal

from backend.models.buro_models import CuentaCartera, RespuestaHDC, TarjetaCredito
from backend.models.enums import Causal
from backend.services.capacidad_pago_service import (
    calcular_capacidad_pago,
    calcular_gastos_financieros,
    calcular_gastos_personales,
    clasificar_obligacion,
    inclusion_gasto_financiero,
    rol_deudor,
)
from backend.services.finanzas import (
    cuota_a_valor_mensual,
    cuota_anualidad,
    valor_presente_anualidad,
)


# ---------------------------------------------------------------------------
# Cuota - amortización francesa
# ---------------------------------------------------------------------------
def test_cuota_formula_francesa():
    cuota = cuota_anualidad(Decimal("1000000"), Decimal("2"), 36)
    assert Decimal("39232") < cuota < Decimal("39234")


def test_cuota_corrige_bug_excel():
    """Cupo 1.000, 2%, 36: la hoja de referencia da 19.5; lo correcto es 39.23."""
    assert round(cuota_anualidad(Decimal("1000"), Decimal("2"), 36), 2) == Decimal("39.23")


def test_cuota_con_tasa_cero():
    assert cuota_anualidad(Decimal("1000000"), Decimal("0"), 10) == Decimal("100000")


def test_cuota_con_plazo_cero():
    assert cuota_anualidad(Decimal("1000000"), Decimal("2"), 0) == Decimal(0)


def test_valor_presente_es_inversa_de_cuota():
    cuota = cuota_anualidad(Decimal("10000000"), Decimal("2"), 24)
    assert abs(valor_presente_anualidad(cuota, Decimal("2"), 24) - Decimal("10000000")) < Decimal("0.01")


def test_cuota_a_valor_mensual():
    assert cuota_a_valor_mensual(Decimal("300000"), "Trimestral") == Decimal("100000")
    assert cuota_a_valor_mensual(Decimal("300000"), "desconocida") == Decimal("300000")
    assert cuota_a_valor_mensual(Decimal("300000"), None) == Decimal("300000")


# ---------------------------------------------------------------------------
# Gastos personales cuando se toma Valor Ingreso (50 / 45 / 40)
# ---------------------------------------------------------------------------
def test_gastos_personales_banda_baja(parametros_demo):
    g = calcular_gastos_personales(Decimal("1000000"), Decimal("200000"), Decimal("0.9"), parametros_demo)
    assert g == Decimal("600000")  # 50% de 1.200.000


def test_gastos_personales_banda_media(parametros_demo):
    g = calcular_gastos_personales(Decimal("1000000"), Decimal("0"), Decimal("1.7"), parametros_demo)
    assert g == Decimal("450000")


def test_gastos_personales_banda_alta(parametros_demo):
    g = calcular_gastos_personales(Decimal("5000000"), Decimal("0"), Decimal("3.5"), parametros_demo)
    assert g == Decimal("2000000")


def test_gastos_personales_incluye_otros_ingresos(parametros_demo):
    g = calcular_gastos_personales(Decimal("2000000"), Decimal("500000"), Decimal("1.7"), parametros_demo)
    assert g == Decimal("1125000")


def test_gastos_personales_frontera_1_6(parametros_demo):
    assert calcular_gastos_personales(Decimal("1000000"), Decimal("0"), Decimal("1.6"), parametros_demo) == Decimal(
        "450000"
    )


def test_gastos_personales_frontera_2_0(parametros_demo):
    assert calcular_gastos_personales(Decimal("1000000"), Decimal("0"), Decimal("2.0"), parametros_demo) == Decimal(
        "400000"
    )


def test_gastos_personales_parametrizables(parametros_demo):
    p = parametros_demo.model_copy(update={"gastos_personales_pct_alto": Decimal("35")})
    assert calcular_gastos_personales(Decimal("1000000"), Decimal("0"), Decimal("2.5"), p) == Decimal("350000")


def test_gastos_personales_quanto_es_50_por_ciento_fijo(parametros_demo):
    assert calcular_gastos_personales(
        Decimal("1000000"), Decimal("0"), Decimal("3.5"), parametros_demo, "quanto3_medio"
    ) == Decimal("500000")


# ---------------------------------------------------------------------------
# Gastos financieros desde HDC+
# ---------------------------------------------------------------------------
def _cartera(**kw) -> CuentaCartera:
    base = dict(tipo_cuenta="CAB", estado_pago="01", cuota=Decimal("100000"), calidad_deudor="00")
    base.update(kw)
    return CuentaCartera(**base)


def test_clasificacion_obligaciones_para_presentacion():
    assert clasificar_obligacion(_cartera(estado_pago="0")) == ("Abierta", "Estado de pago vigente 00")
    assert clasificar_obligacion(_cartera(estado_pago="03")) == ("Cerrada", "Estado de pago 03")
    assert clasificar_obligacion(_cartera(estado_pago="01", bloqueada=True))[0] == "Excluida"
    assert clasificar_obligacion(_cartera(estado_pago="99"))[0] == "Excluida"


def test_rol_e_inclusion_financiera_codeudor():
    tarjeta = TarjetaCredito(estado_pago="01", calidad_deudor="01", cuota=Decimal("30000"))
    assert clasificar_obligacion(tarjeta) == ("Abierta", "Estado de pago vigente 01")
    assert rol_deudor(tarjeta) == "Codeudor"
    assert inclusion_gasto_financiero(tarjeta) == (False, "La persona figura como codeudora")


def test_roles_deudor_normalizados():
    assert rol_deudor(_cartera(calidad_deudor="00")) == "Principal"
    assert rol_deudor(_cartera(calidad_deudor="Principal")) == "Principal"
    assert rol_deudor(_cartera(calidad_deudor=None)) == "No reportado"
    assert rol_deudor(_cartera(calidad_deudor="AVALISTA")) == "Otro"


def test_gastos_financieros_separa_rotativos(parametros_demo):
    hdc = RespuestaHDC(
        cuentas_cartera=[_cartera(), _cartera(tipo_cuenta="CBR", cuota=Decimal("50000"))],
        tarjetas_credito=[TarjetaCredito(estado_pago="01", cuota=Decimal("30000"))],
    )
    no_rot, rot = calcular_gastos_financieros(hdc, parametros_demo)
    assert no_rot == Decimal("100000")
    assert rot == Decimal("80000")


def test_gastos_financieros_excluye_codeudor_bloqueada_y_cerrada(parametros_demo):
    hdc = RespuestaHDC(
        cuentas_cartera=[
            _cartera(calidad_deudor="01"),
            _cartera(bloqueada=True),
            _cartera(estado_pago="03"),  # pago total: cerrada
        ]
    )
    assert calcular_gastos_financieros(hdc, parametros_demo) == (Decimal(0), Decimal(0))


def test_gastos_financieros_estima_cuota_sin_reporte(parametros_demo):
    hdc = RespuestaHDC(
        cuentas_cartera=[
            _cartera(
                cuota=Decimal(0),
                saldo_actual=Decimal("1000000"),
                fecha_apertura=date(2024, 1, 1),
                fecha_vencimiento=date(2027, 1, 1),
            ),
        ],
        tarjetas_credito=[TarjetaCredito(estado_pago="01", saldo_actual=Decimal("1000000"))],
    )
    no_rot, rot = calcular_gastos_financieros(hdc, parametros_demo)
    assert no_rot > 0
    assert rot == cuota_anualidad(Decimal("1000000"), Decimal("2"), 36)


def test_gastos_financieros_reconoce_codigo_cartera_rotativa_3(parametros_demo):
    hdc = RespuestaHDC(cuentas_cartera=[_cartera(tipo_cuenta="3", cuota=Decimal(0), saldo_actual=Decimal("1000000"))])
    _, rot = calcular_gastos_financieros(hdc, parametros_demo)
    assert rot == cuota_anualidad(Decimal("1000000"), Decimal("2"), 36)


def test_gastos_financieros_rotativo_sin_cuota_usa_cupo(parametros_demo):
    hdc = RespuestaHDC(
        tarjetas_credito=[
            TarjetaCredito(
                estado_pago="01",
                cuota=Decimal(0),
                saldo_actual=Decimal("9000000"),
                cupo_total=Decimal("13050000"),
            )
        ]
    )
    _, rot = calcular_gastos_financieros(hdc, parametros_demo)
    assert rot == cuota_anualidad(Decimal("13050000"), Decimal("2"), 36)


def test_gastos_financieros_excluye_rotativo_cerrado_por_descripcion(parametros_demo):
    hdc = RespuestaHDC(
        tarjetas_credito=[
            TarjetaCredito(
                estado_pago="01",
                estado_cuenta_desc="Pagó Vol Obligación Normal",
                saldo_actual=Decimal("9000000"),
                cupo_total=Decimal("13050000"),
            )
        ]
    )
    assert calcular_gastos_financieros(hdc, parametros_demo) == (Decimal(0), Decimal(0))


def test_gastos_financieros_excluye_tarjeta_cancelada_por_evento_05(parametros_demo):
    tarjeta = TarjetaCredito(
        estado_pago="00",
        estado_cuenta_desc="NO REPORTO",
        evento_buro="05",
        saldo_actual=Decimal("9000000"),
        cupo_total=Decimal("13050000"),
    )
    assert clasificar_obligacion(tarjeta) == ("Cerrada", "Evento de cierre de tarjeta 05")
    assert calcular_gastos_financieros(RespuestaHDC(tarjetas_credito=[tarjeta]), parametros_demo) == (
        Decimal(0),
        Decimal(0),
    )


def test_evento_05_no_cierra_cartera(parametros_demo):
    cuenta = _cartera(evento_buro="05")
    assert clasificar_obligacion(cuenta) == ("Abierta", "Estado de pago vigente 01")
    assert calcular_gastos_financieros(RespuestaHDC(cuentas_cartera=[cuenta]), parametros_demo) == (
        Decimal("100000"),
        Decimal(0),
    )


def test_gastos_financieros_excluye_cartera_cerrada_por_estado_origen(parametros_demo):
    hdc = RespuestaHDC(
        cuentas_cartera=[
            _cartera(
                tipo_cuenta="3",
                estado_pago="01",
                estado_origen="03",
                valor_inicial=Decimal("13050000"),
            )
        ]
    )
    assert calcular_gastos_financieros(hdc, parametros_demo) == (Decimal(0), Decimal(0))


def test_gastos_financieros_acepta_estado_activo_cero(parametros_demo):
    hdc = RespuestaHDC(tarjetas_credito=[TarjetaCredito(estado_pago="0", cuota=Decimal("30000"))])
    assert calcular_gastos_financieros(hdc, parametros_demo)[1] == Decimal("30000")


def test_gastos_financieros_convierte_periodicidad(parametros_demo):
    hdc = RespuestaHDC(cuentas_cartera=[_cartera(cuota=Decimal("600000"), forma_pago="Semestral")])
    assert calcular_gastos_financieros(hdc, parametros_demo)[0] == Decimal("100000")


# ---------------------------------------------------------------------------
# Capacidad de pago y decisiones
# ---------------------------------------------------------------------------
def test_capacidad_pago_sana(parametros_demo, solicitud_empleado):
    r = calcular_capacidad_pago(RespuestaHDC(), solicitud_empleado, parametros_demo, Decimal("5000000"), Decimal("3.8"))
    assert r.gastos_personales == Decimal("2000000")
    assert r.endeudamiento == Decimal("40")
    assert r.disponible == Decimal("3000000")
    assert r.capacidad_pago == Decimal("2100000")
    assert r.cupo_sugerido == Decimal("20000000")  # tope aprobado
    assert r.cuota_sugerida < r.capacidad_pago
    assert r.causales == []


def test_endeudamiento_entre_86_y_90_rechaza(parametros_demo, solicitud_empleado):
    hdc = RespuestaHDC(cuentas_cartera=[_cartera(cuota=Decimal("2300000"))])
    r = calcular_capacidad_pago(hdc, solicitud_empleado, parametros_demo, Decimal("5000000"), Decimal("3.8"))
    assert r.endeudamiento == Decimal("86")
    assert r.causales == [Causal.R17]


def test_endeudamiento_mayor_90_rechaza(parametros_demo, solicitud_empleado):
    hdc = RespuestaHDC(cuentas_cartera=[_cartera(cuota=Decimal("2300000"))])
    r = calcular_capacidad_pago(hdc, solicitud_empleado, parametros_demo, Decimal("5000000"), Decimal("3.8"))
    assert Causal.R17 in r.causales
    assert Causal.E8 not in r.causales  # si hay rechazo no se agregan estudios


def test_sin_disponible_rechaza(parametros_demo, solicitud_empleado):
    hdc = RespuestaHDC(cuentas_cartera=[_cartera(cuota=Decimal("3000000"))])
    r = calcular_capacidad_pago(hdc, solicitud_empleado, parametros_demo, Decimal("5000000"), Decimal("3.8"))
    assert {Causal.R18, Causal.R19, Causal.R17} <= set(r.causales)


def test_cuota_moto_supera_capacidad_es_estudio(parametros_demo, solicitud_empleado):
    s = solicitud_empleado.model_copy(update={"saldo_financiar": Decimal("100000000")})
    r = calcular_capacidad_pago(RespuestaHDC(), s, parametros_demo, Decimal("5000000"), Decimal("3.8"))
    assert r.causales == [Causal.E9]
