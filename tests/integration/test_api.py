"""Pruebas de la API completa (FastAPI + SQLite en memoria + escenarios demo)."""

import pytest
from decimal import Decimal

from backend.db_models import session as db_session
from backend.db_models.models import (
    AliadoFinanciero,
    AliadoProducto,
    AliadoReglaElegibilidad,
    Banco,
    CapacidadPago,
    Cotizante,
    CotizanteIngresoMensual,
    CreditoFinanciacion,
    CuentaBancaria,
    Desembolso,
    EvaluacionCredito,
    ProductoVehiculo,
    SolicitudCausal,
    SolicitudCredito,
)
from backend.services.finanzas import cuota_anualidad
from tests.integration.conftest import PAYLOAD

ESPERADO = {
    "aprobado": ("Aprobado", []),
    "score_bajo": ("Rechazado", ["R14"]),
    "sin_experiencia": ("Rechazado", ["R23"]),
    "fallecido": ("Rechazado", ["R1", "R12"]),
    "exclusion_score": ("Rechazado", ["E7"]),
    "mora_90": ("Rechazado", ["R6", "R9", "R10"]),
    "embargo": ("Rechazado", ["R2"]),
    "castigada": ("Rechazado", ["R4"]),
    "mora_30": ("Rechazado", ["E2"]),
    "perfil_bajo": ("Rechazado", ["E4"]),
    "sin_valor_ingreso": ("Rechazado", ["RC1"]),
    "endeudamiento_alto": ("Rechazado", ["R17"]),
}


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok" and r.json()["environment"] == "demo"


def test_todos_los_escenarios_tienen_resultado_esperado(client):
    assert set(client.get("/api/motor/escenarios").json()) == set(ESPERADO)
    for escenario, (decision, causales) in ESPERADO.items():
        r = client.post("/api/motor/evaluar", json={**PAYLOAD, "escenario_mock": escenario})
        assert r.status_code == 200, (escenario, r.text)
        data = r.json()
        assert data["decision"] == decision, escenario
        assert [c["codigo"] for c in data["causales"]] == causales, escenario


def test_respuesta_no_expone_reportes_del_buro(client):
    data = client.post("/api/motor/evaluar", json=PAYLOAD).json()
    assert "hdc_respuesta" not in data
    valor_ingreso = data["valor_ingreso_respuesta"]
    assert valor_ingreso["resumen_general"]["promedio_ingresos_cotizante"] == 0
    assert valor_ingreso["aportantes"][0]["razon_social"] == "EMPLEADOR FICTICIO S.A.S."
    assert valor_ingreso["aportantes"][0]["tipo_cotizante"] == 1
    assert valor_ingreso["aportantes"][0]["resultado_pagos"]
    assert data["trazabilidad"] and "indicadores_buro" in data
    assert data["indicadores_buro"]["quanto"]["valor_medio"] == 5000000
    assert data["quanto_medio"] == "5000000.00"
    assert data["valor_ingreso"] == "5000000.00"
    assert data["ingreso_final"] == "5000000.00"
    assert data["gastos_personales"] == "2000000.00"
    assert data["endeudamiento"] == "40.00"
    assert data["disponible"] == "3000000.00"
    assert data["capacidad_pago"] == "2100000.00"
    assert data["cupo_sugerido"] == "20000000.00"


@pytest.mark.parametrize("cambio", [{"plazo": 0}, {"saldo_financiar": 0}, {"tasa": -1}, {"ocupacion": "Otro"}])
def test_validacion_de_entrada(client, cambio):
    assert client.post("/api/motor/evaluar", json={**PAYLOAD, **cambio}).status_code == 422


def test_escenario_inexistente(client):
    r = client.post("/api/motor/evaluar", json={**PAYLOAD, "escenario_mock": "nada"})
    assert r.status_code == 422 and r.json()["error"] == "validacion"


def test_consulta_experian_sin_credenciales(client):
    r = client.post("/api/motor/evaluar", json={**PAYLOAD, "consultar_experian": True})
    assert r.status_code == 502
    assert "HDC_USERNAME" in r.json()["detail"]


def test_auditoria(client):
    ev = client.post("/api/motor/evaluar", json={**PAYLOAD, "escenario_mock": "embargo"}).json()
    client.post("/api/motor/evaluar", json=PAYLOAD)
    todos = client.get("/api/auditoria").json()
    assert len(todos) == 2
    rechazados = client.get("/api/auditoria", params={"decision": "Rechazado"}).json()
    assert [r["evaluacion_id"] for r in rechazados] == [ev["evaluacion_id"]]
    assert rechazados[0]["origen_datos"] == "mock:embargo"
    detalle = client.get(f"/api/auditoria/{ev['evaluacion_id']}").json()
    assert detalle["causales"][0]["codigo"] == "R2"
    assert "hdc_respuesta" not in detalle["resultado"]
    assert detalle["parametros_huella"] == todos[0]["parametros_huella"]
    assert len(detalle["parametros_huella"]) == 16
    assert client.get("/api/auditoria/no-existe").status_code == 404


def test_parametros(client):
    assert client.get("/api/parametros").json()["parametros"]["endeu_2"] == 86
    assert client.put("/api/parametros", json={"endeu_2": 95}).status_code == 422
    assert client.put("/api/parametros", json={}).status_code == 422
    assert client.put("/api/parametros", json={"no_existe": 1}).status_code == 422
    assert client.put("/api/parametros", json={"endeu_2": 35}).json()["parametros"]["endeu_2"] == 35
    # el cambio aplica en la siguiente evaluación: endeudamiento 40% >= 35% -> R17
    data = client.post("/api/motor/evaluar", json=PAYLOAD).json()
    assert [c["codigo"] for c in data["causales"]] == ["R17"]
    assert client.post("/api/parametros/reset").json()["parametros"]["endeu_2"] == 86


SOLICITUD = {
    "cliente": {
        "tipo_documento": "1",
        "num_cedula": "1000000001",
        "nombre_completo": "Cliente Ficticio",
        "primer_apellido": "Ficticio",
        "fecha_nacimiento": "1990-05-15",
        "ocupacion": "Empleado",
    },
    "datos_laborales": {"tipo_contrato": "Indefinido", "ingreso_mensual": 5000000},
}
CREDITO = {"saldo_financiar": 10000000, "plazo": 36, "tasa": 2}


def _crear_solicitud(client) -> str:
    r = client.post("/api/solicitudes", json=SOLICITUD)
    assert r.status_code == 201, r.text
    return r.json()["id_solicitud"]


def test_flujo_solicitud_persistida(client):
    id_solicitud = _crear_solicitud(client)
    r1 = client.post(f"/api/solicitudes/{id_solicitud}/evaluar", json=CREDITO)
    assert r1.status_code == 200 and r1.json()["decision"] == "Aprobado"
    assert r1.json()["id_solicitud"] == id_solicitud
    r2 = client.post(f"/api/solicitudes/{id_solicitud}/evaluar", json={**CREDITO, "escenario_mock": "embargo"})
    assert r2.json()["decision"] == "Rechazado"

    db = db_session.SessionLocal()
    try:
        evaluaciones = db.query(EvaluacionCredito).order_by(EvaluacionCredito.version).all()
        assert [(e.version, e.vigente) for e in evaluaciones] == [(1, False), (2, True)]
        assert evaluaciones[1].embargo == 1 and evaluaciones[1].decision_interna == "Rechazado"
        assert [(c.version, c.vigente) for c in db.query(CapacidadPago).order_by(CapacidadPago.version)] == [
            (1, False),
            (2, True),
        ]
        assert [(c.codigo, c.activa) for c in db.query(SolicitudCausal)] == [("R2", True)]
        solicitud = db.query(SolicitudCredito).one()
        assert solicitud.decision == "rechazado"
    finally:
        db.close()
    assert len(client.get("/api/auditoria", params={"numero_id": "1000000001"}).json()) == 2


def test_solicitud_inexistente_y_apellido_faltante(client):
    assert client.post("/api/solicitudes/00000000-0000-0000-0000-000000000000/evaluar", json=CREDITO).status_code == 404
    sin_apellido = {**SOLICITUD, "cliente": {**SOLICITUD["cliente"]}}
    sin_apellido["cliente"].pop("primer_apellido")
    assert client.post("/api/solicitudes", json=sin_apellido).status_code == 422


def test_elegibilidad_y_seleccion_de_oferta(client):
    db = db_session.SessionLocal()
    aliado = AliadoFinanciero(nit="900000000", nombre="Aliado Ficticio", tipo="banco")
    db.add(aliado)
    db.flush()
    p_ok = AliadoProducto(id_aliado=aliado.id_aliado, nombre="Producto A")
    p_no = AliadoProducto(id_aliado=aliado.id_aliado, nombre="Producto B")
    db.add_all([p_ok, p_no])
    db.flush()
    db.add_all(
        [
            AliadoReglaElegibilidad(
                id_aliado_producto=p_ok.id_aliado_producto, campo="score", operador=">=", valor_json=700
            ),
            AliadoReglaElegibilidad(
                id_aliado_producto=p_no.id_aliado_producto, campo="ingreso_final_smmlv", operador=">=", valor_json=10
            ),
        ]
    )
    db.commit()
    db.close()

    id_solicitud = _crear_solicitud(client)
    assert client.post(f"/api/solicitudes/{id_solicitud}/evaluar", json=CREDITO).json()["decision"] == "Aprobado"
    ofertas = client.get(f"/api/solicitudes/{id_solicitud}/ofertas").json()
    assert sorted(o["elegible"] for o in ofertas) == [False, True]
    elegible = next(o for o in ofertas if o["elegible"])
    no_elegible = next(o for o in ofertas if not o["elegible"])
    r = client.post(f"/api/solicitudes/{id_solicitud}/ofertas/seleccionar", json={"id_oferta": elegible["id_oferta"]})
    assert r.status_code == 200 and r.json()["seleccionada"] is True
    r = client.post(f"/api/solicitudes/{id_solicitud}/ofertas/seleccionar", json={"id_oferta": no_elegible["id_oferta"]})
    assert r.status_code == 422
    assert client.post(f"/api/solicitudes/{id_solicitud}/ofertas/seleccionar", json={"id_oferta": 9999}).status_code == 404


def test_seleccion_oferta_con_monto_y_plazo(client):
    """El cliente puede tomar menos del cupo aprobado y un plazo más
    corto; la oferta seleccionada queda con esos términos y la cuota
    recalculada. Exceder el cupo o el plazo vigentes -> 422."""
    db = db_session.SessionLocal()
    aliado = AliadoFinanciero(nit="900000001", nombre="Aliado Monto", tipo="banco")
    db.add(aliado)
    db.flush()
    db.add(AliadoProducto(id_aliado=aliado.id_aliado, nombre="Producto A"))
    db.commit()
    db.close()

    id_solicitud = _crear_solicitud(client)
    assert client.post(f"/api/solicitudes/{id_solicitud}/evaluar", json=CREDITO).json()["decision"] == "Aprobado"
    ofertas = client.get(f"/api/solicitudes/{id_solicitud}/ofertas").json()
    elegible = next(o for o in ofertas if o["elegible"])
    cupo = float(elegible["monto_aprobado"])
    assert cupo > 0

    # Monto por encima del cupo aprobado -> 422
    r = client.post(
        f"/api/solicitudes/{id_solicitud}/ofertas/seleccionar",
        json={"id_oferta": elegible["id_oferta"], "monto": cupo + 1},
    )
    assert r.status_code == 422

    # Monto y plazo menores -> se conservan en la oferta y la cuota baja
    r = client.post(
        f"/api/solicitudes/{id_solicitud}/ofertas/seleccionar",
        json={
            "id_oferta": elegible["id_oferta"],
            "monto": cupo / 2,
            "plazo": 12,
        },
    )
    assert r.status_code == 200, r.text
    oferta = r.json()
    assert oferta["seleccionada"] is True
    assert float(oferta["monto_aprobado"]) == cupo / 2
    assert oferta["plazo_ofrecido"] == 12
    tasa = float(elegible["tasa_ofrecida"])
    cuota_esperada = float(
        cuota_anualidad(Decimal(str(cupo / 2)), Decimal(str(tasa)), 12)
    )
    assert float(oferta["cuota_mensual"]) == cuota_esperada


def test_listar_solicitudes(client):
    id_solicitud = _crear_solicitud(client)
    lista = client.get("/api/solicitudes").json()
    assert len(lista) == 1
    s = lista[0]
    assert s["id_solicitud"] == id_solicitud
    # num_solicitud lo genera una secuencia de Postgres; en SQLite queda NULL.
    assert "num_solicitud" in s
    assert s["nombre_cliente"] == "Cliente Ficticio"
    assert s["num_cedula"] == "1000000001"
    assert s["estado"] == "creada"
    assert s["decision"] is None
    assert s["evaluacion"] is None


def test_listar_solicitudes_filtros(client):
    _crear_solicitud(client)
    assert len(client.get("/api/solicitudes", params={"busqueda": "ficticio"}).json()) == 1
    assert len(client.get("/api/solicitudes", params={"busqueda": "1000000001"}).json()) == 1
    assert len(client.get("/api/solicitudes", params={"busqueda": "no-existe"}).json()) == 0
    assert len(client.get("/api/solicitudes", params={"estado": "rechazada"}).json()) == 0
    assert len(client.get("/api/solicitudes", params={"decision": "aprobado"}).json()) == 0
    assert len(client.get("/api/solicitudes", params={"limite": 0}).json()) == 0


def test_listar_refleja_evaluacion_vigente(client):
    id_solicitud = _crear_solicitud(client)
    client.post(f"/api/solicitudes/{id_solicitud}/evaluar", json=CREDITO)
    client.post(
        f"/api/solicitudes/{id_solicitud}/evaluar",
        json={**CREDITO, "escenario_mock": "embargo"},
    )
    [s] = client.get("/api/solicitudes").json()
    assert s["decision"] == "rechazado"
    ev = s["evaluacion"]
    assert ev["version"] == 2
    assert ev["decision_interna"] == "Rechazado"
    assert ev["score"] is not None
    assert ev["cupo_sugerido"] is not None
    assert len(client.get("/api/solicitudes", params={"decision": "rechazado"}).json()) == 1


def test_crear_solicitud_actualiza_ocupacion_cliente_existente(client):
    """La ocupación es situación laboral actual: una solicitud nueva
    para un cliente existente la actualiza (evita evaluar con la
    matriz equivocada por un registro previo)."""
    _crear_solicitud(client)  # Empleado
    sol_independiente = {
        **SOLICITUD,
        "cliente": {**SOLICITUD["cliente"], "ocupacion": "Independiente"},
        "datos_laborales": {
            "tipo_contrato": None,
            "ingreso_mensual": 5000000,
            "anios_camara_comercio": 5,
        },
    }
    r = client.post("/api/solicitudes", json=sol_independiente)
    assert r.status_code == 201, r.text

    db = db_session.SessionLocal()
    try:
        from backend.db_models.models import Cliente

        cliente = db.query(Cliente).one()
        assert cliente.ocupacion == "independiente"
        assert db.query(SolicitudCredito).count() == 2
    finally:
        db.close()


def test_detalle_solicitud(client):
    id_solicitud = _crear_solicitud(client)
    client.post(
        f"/api/solicitudes/{id_solicitud}/evaluar",
        json={**CREDITO, "escenario_mock": "embargo"},
    )
    d = client.get(f"/api/solicitudes/{id_solicitud}").json()
    assert d["id_solicitud"] == id_solicitud
    assert d["nombre_cliente"] == "Cliente Ficticio"
    assert d["datos_laborales"]["ingreso_mensual"] == "5000000.00"
    assert d["datos_laborales"]["tipo_contrato"] == "indefinido"
    assert [c["codigo"] for c in d["causales"]] == ["R2"]
    assert d["evaluacion"]["decision_interna"] == "Rechazado"
    assert d["ofertas"] == []
    assert (
        client.get("/api/solicitudes/00000000-0000-0000-0000-000000000000").status_code
        == 404
    )


@pytest.mark.parametrize("ocupacion", ["Pensionado", "Fuerzas Militares"])
def test_evaluacion_pensionado_y_ffmm(client, ocupacion):
    """La ocupación de la solicitud persistida enruta a la matriz
    correcta del motor (PPT v4): ALTO con score A aprueba."""
    sol = {
        **SOLICITUD,
        "cliente": {**SOLICITUD["cliente"], "ocupacion": ocupacion},
        "datos_laborales": {"tipo_contrato": "NA", "ingreso_mensual": 5000000},
    }
    r = client.post("/api/solicitudes", json=sol)
    assert r.status_code == 201, r.text
    id_solicitud = r.json()["id_solicitud"]
    ev = client.post(f"/api/solicitudes/{id_solicitud}/evaluar", json=CREDITO).json()
    assert ev["decision"] == "Aprobado"
    assert ev["perfil_score"] == "A"
    assert ev["perfil_ingreso"] == "ALTO"


def test_catalogo_productos(client):
    db = db_session.SessionLocal()
    aliado = AliadoFinanciero(nit="900000000", nombre="Aliado Ficticio", tipo="banco")
    db.add(aliado)
    db.flush()
    db.add(
        AliadoProducto(
            id_aliado=aliado.id_aliado,
            nombre="Producto Moto",
            tasa_min=1.5,
            tasa_max=2.2,
            plazo_min_meses=12,
            plazo_max_meses=48,
            monto_min=500000,
            monto_max=20000000,
        )
    )
    db.commit()
    db.close()

    productos = client.get("/api/productos").json()
    assert len(productos) == 1
    p = productos[0]
    assert p["nombre"] == "Producto Moto"
    assert p["aliado"] == "Aliado Ficticio"
    assert float(p["tasa_min"]) == 1.5
    assert p["plazo_max_meses"] == 48
    assert p["monto_max"] == "20000000.00"


def test_valor_ingreso_desde_cotizantes(client):
    from datetime import date

    id_solicitud = _crear_solicitud(client)
    import uuid

    db = db_session.SessionLocal()
    cot = Cotizante(id_solicitud=uuid.UUID(id_solicitud), razon_social_aportante="Empresa", meses_continuidad=12)
    db.add(cot)
    db.flush()
    for mes, valor in ((9, 3000000), (8, 3000000), (7, 0), (6, 9000000)):
        db.add(CotizanteIngresoMensual(id_cotizante=cot.id_cotizante, periodo=date(2026, mes, 1), ingreso=valor))
    db.commit()
    db.close()

    r = client.post("/api/motor/ingreso", json={"id_solicitud": id_solicitud})
    assert r.status_code == 200
    assert r.json()["valor_ingreso"] == "2000000.00"  # últimos 3 períodos consecutivos, incluido el cero
    # En la evaluación demo, los cotizantes almacenados reemplazan el Valor Ingreso ficticio
    ev = client.post(f"/api/solicitudes/{id_solicitud}/evaluar", json=CREDITO).json()
    assert ev["valor_ingreso"] == "2000000.00"
    auditoria = client.get("/api/auditoria").json()[0]
    assert auditoria["origen_datos"] == "mock:aprobado+cotizantes"


# ---------------------------------------------------------------------------
# Desembolso (D55): producto_vehiculo -> credito_financiacion -> desembolso
# ---------------------------------------------------------------------------
DESEMBOLSO = {
    "codigo_ach_banco": "007",
    "numero_cuenta_cliente": "12345678901",
    "referencia_pago": "TRX-TEST-1",
}


def _sembrar_cadena_desembolso(db, con_cuenta_emisora=True):
    """Banco + aliado propio (con cuenta emisora) + producto elegible."""
    banco = Banco(codigo_ach="007", nombre="BANCOLOMBIA", nit="890903938")
    aliado = AliadoFinanciero(
        nit="814005081", nombre="INVERSIONES PACIFICO S.A.", tipo="otro", es_propio=True
    )
    db.add_all([banco, aliado])
    db.flush()
    if con_cuenta_emisora:
        db.add(
            CuentaBancaria(
                id_banco=banco.id_banco,
                tipo="ahorros",
                numero="0000000000",
                titular="INVERSIONES PACIFICO S.A.",
                nit_titular="814005081",
                id_aliado=aliado.id_aliado,
            )
        )
    db.add(
        AliadoProducto(
            id_aliado=aliado.id_aliado,
            nombre="Producto Moto",
            tasa_min=1.5,
            tasa_max=2.2,
            plazo_min_meses=12,
            plazo_max_meses=48,
            monto_min=500000,
            monto_max=20000000,
        )
    )
    db.commit()


def _solicitud_aprobada_con_oferta(client) -> str:
    id_solicitud = _crear_solicitud(client)
    ev = client.post(f"/api/solicitudes/{id_solicitud}/evaluar", json=CREDITO).json()
    assert ev["decision"] == "Aprobado"
    ofertas = client.get(f"/api/solicitudes/{id_solicitud}/ofertas").json()
    elegible = next(o for o in ofertas if o["elegible"])
    r = client.post(
        f"/api/solicitudes/{id_solicitud}/ofertas/seleccionar",
        json={"id_oferta": elegible["id_oferta"]},
    )
    assert r.status_code == 200
    return id_solicitud


def test_desembolso_flujo_completo(client):
    db = db_session.SessionLocal()
    _sembrar_cadena_desembolso(db)
    db.close()

    id_solicitud = _solicitud_aprobada_con_oferta(client)
    r = client.post(f"/api/solicitudes/{id_solicitud}/desembolso", json=DESEMBOLSO)
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["estado"] == "confirmado"
    assert d["num_desembolso"].startswith("DES-")
    assert d["emisor"] == "INVERSIONES PACIFICO S.A."
    assert d["receptor"] == "Cliente Ficticio"
    assert d["capital"] == "20000000.00"  # cupo del motor acotado a monto_max
    assert d["plazo"] == 36 and d["tasa"] == "1.5000"
    assert d["referencia_pago"] == "TRX-TEST-1"
    assert d["fecha_desembolso"] is not None

    assert client.get(f"/api/solicitudes/{id_solicitud}").json()["estado"] == "desembolsada"

    db = db_session.SessionLocal()
    try:
        credito = db.query(CreditoFinanciacion).one()
        assert credito.ganadora is True
        assert credito.valor_financiacion == 20000000
        assert credito.fecha_inicio is not None and credito.fecha_fin is not None
        assert db.query(ProductoVehiculo).one().id_solicitud == credito.id_solicitud
        desembolso = db.query(Desembolso).one()
        cuenta_cliente = db.query(CuentaBancaria).filter(CuentaBancaria.id_cliente.isnot(None)).one()
        assert desembolso.id_cuenta_receptor == cuenta_cliente.id_cuenta
        assert desembolso.id_cuenta_emisor != desembolso.id_cuenta_receptor
    finally:
        db.close()


def test_desembolso_idempotente(client):
    db = db_session.SessionLocal()
    _sembrar_cadena_desembolso(db)
    db.close()

    id_solicitud = _solicitud_aprobada_con_oferta(client)
    r1 = client.post(f"/api/solicitudes/{id_solicitud}/desembolso", json=DESEMBOLSO)
    r2 = client.post(f"/api/solicitudes/{id_solicitud}/desembolso", json=DESEMBOLSO)
    assert r1.status_code == 201 and r2.status_code == 201
    assert r2.json()["id_desembolso"] == r1.json()["id_desembolso"]

    db = db_session.SessionLocal()
    try:
        assert db.query(Desembolso).count() == 1
        assert db.query(CreditoFinanciacion).count() == 1
    finally:
        db.close()


def test_desembolso_validaciones(client):
    db = db_session.SessionLocal()
    _sembrar_cadena_desembolso(db)
    db.close()

    # solicitud inexistente -> 404
    assert (
        client.post(
            "/api/solicitudes/00000000-0000-0000-0000-000000000000/desembolso",
            json=DESEMBOLSO,
        ).status_code
        == 404
    )

    # solicitud sin evaluar -> 422
    id_solicitud = _crear_solicitud(client)
    assert (
        client.post(f"/api/solicitudes/{id_solicitud}/desembolso", json=DESEMBOLSO).status_code
        == 422
    )

    # solicitud rechazada -> 422
    client.post(
        f"/api/solicitudes/{id_solicitud}/evaluar",
        json={**CREDITO, "escenario_mock": "embargo"},
    )
    assert (
        client.post(f"/api/solicitudes/{id_solicitud}/desembolso", json=DESEMBOLSO).status_code
        == 422
    )


def test_desembolso_sin_oferta_seleccionada(client):
    db = db_session.SessionLocal()
    _sembrar_cadena_desembolso(db)
    db.close()

    id_solicitud = _crear_solicitud(client)
    ev = client.post(f"/api/solicitudes/{id_solicitud}/evaluar", json=CREDITO).json()
    assert ev["decision"] == "Aprobado"
    r = client.post(f"/api/solicitudes/{id_solicitud}/desembolso", json=DESEMBOLSO)
    assert r.status_code == 422
    assert "oferta seleccionada" in r.json()["detail"]


def test_desembolso_banco_y_cuenta_invalidos(client):
    db = db_session.SessionLocal()
    _sembrar_cadena_desembolso(db)
    db.close()

    id_solicitud = _solicitud_aprobada_con_oferta(client)

    # banco no registrado -> 422
    r = client.post(
        f"/api/solicitudes/{id_solicitud}/desembolso",
        json={**DESEMBOLSO, "codigo_ach_banco": "999"},
    )
    assert r.status_code == 422

    # cuenta registrada a nombre de otro cliente -> 422
    db = db_session.SessionLocal()
    banco = db.query(Banco).one()
    db.add(
        CuentaBancaria(
            id_banco=banco.id_banco,
            tipo="ahorros",
            numero="999888777",
            titular="Otra Persona",
            id_cliente=999999,
        )
    )
    db.commit()
    db.close()
    r = client.post(
        f"/api/solicitudes/{id_solicitud}/desembolso",
        json={**DESEMBOLSO, "numero_cuenta_cliente": "999888777"},
    )
    assert r.status_code == 422
    assert "no pertenece al cliente" in r.json()["detail"]


def test_desembolso_sin_cuenta_emisora(client):
    db = db_session.SessionLocal()
    _sembrar_cadena_desembolso(db, con_cuenta_emisora=False)
    db.close()

    id_solicitud = _solicitud_aprobada_con_oferta(client)
    r = client.post(f"/api/solicitudes/{id_solicitud}/desembolso", json=DESEMBOLSO)
    assert r.status_code == 422
    assert "aliado financiero propio" in r.json()["detail"]


def test_desembolso_confirma_pendiente_existente(client):
    """Un crédito formalizado con desembolso 'pendiente' se confirma al
    llamar el endpoint (caso de reproceso tras una falla operativa)."""
    db = db_session.SessionLocal()
    _sembrar_cadena_desembolso(db)
    db.close()

    id_solicitud = _solicitud_aprobada_con_oferta(client)

    import uuid as _uuid

    db = db_session.SessionLocal()
    vehiculo = ProductoVehiculo(id_solicitud=_uuid.UUID(id_solicitud), producto_a_financiar="Moto")
    db.add(vehiculo)
    db.flush()
    credito = CreditoFinanciacion(
        id_solicitud=_uuid.UUID(id_solicitud),
        id_vehiculo=vehiculo.id_vehiculo,
        ganadora=True,
        tasa=1.5,
        plazo=36,
        valor_financiar=10000000,
        saldo_financiar=10000000,
        valor_financiacion=10000000,
        total_a_pagar=10800000,
        cuota_financiacion=300000,
        cuota_total=300000,
    )
    db.add(credito)
    db.flush()
    emisor = db.query(CuentaBancaria).filter(CuentaBancaria.id_aliado.isnot(None)).one()
    banco = db.query(Banco).one()
    receptor = CuentaBancaria(
        id_banco=banco.id_banco,
        tipo="ahorros",
        numero=DESEMBOLSO["numero_cuenta_cliente"],
        titular="Cliente Ficticio",
        id_cliente=db.query(SolicitudCredito).one().id_cliente,
    )
    db.add(receptor)
    db.flush()
    db.add(
        Desembolso(
            id_credito=credito.id_credito,
            id_cuenta_emisor=emisor.id_cuenta,
            emisor=emisor.titular,
            id_cuenta_receptor=receptor.id_cuenta,
            receptor=receptor.titular,
            capital=10000000,
            cuota=300000,
            plazo=36,
            tasa=1.5,
            estado="pendiente",
        )
    )
    db.commit()
    db.close()

    r = client.post(f"/api/solicitudes/{id_solicitud}/desembolso", json=DESEMBOLSO)
    assert r.status_code == 201
    d = r.json()
    assert d["estado"] == "confirmado"
    assert d["fecha_desembolso"] is not None
    assert d["capital"] == "10000000.00"
