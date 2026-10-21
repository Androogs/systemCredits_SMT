"""Pruebas de la API completa (FastAPI + SQLite en memoria + escenarios demo)."""

import pytest
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.db_models import session as db_session
from backend.db_models.models import (
    AliadoFinanciero,
    AliadoProducto,
    AliadoReglaElegibilidad,
    Aseguradora,
    Banco,
    CapacidadPago,
    Cotizante,
    CotizanteIngresoMensual,
    CreditoFinanciacion,
    CuentaBancaria,
    Desembolso,
    EvaluacionCredito,
    OfertaCredito,
    ProductoVehiculo,
    SeguroProducto,
    SolicitudCausal,
    SolicitudCredito,
)
from backend.db_models.evidencia_models import DocumentoEvidencia
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
    "perfil_bajo": ("Aprobado", ["E4"]),
    "sin_valor_ingreso": ("Rechazado", ["RC1"]),
    "endeudamiento_alto": ("Rechazado", ["R17"]),
    # El pre-filtro SIMIT corre antes del buró: deuda pendiente -> R22
    # sin que se llegue a construir el escenario del buró.
    "simit_multas": ("Rechazado", ["R22"]),
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


def test_evaluar_rechaza_tasa_sobre_usura(client):
    """Guarda de cumplimiento: la tasa nunca iguala ni supera la usura
    de la modalidad que aplica al monto (stub SFC en conftest)."""
    id_solicitud = _crear_solicitud(client)
    # 10M > 6 SMMLV (7,8M en pruebas): aplica usura ordinario 2,1176% m.v.
    r = client.post(
        f"/api/solicitudes/{id_solicitud}/evaluar",
        json={**CREDITO, "tasa": 2.1176},
    )
    assert r.status_code == 422
    assert "usura" in r.json()["detail"].lower()

    # Justo por debajo del límite sí evalúa.
    ok = client.post(
        f"/api/solicitudes/{id_solicitud}/evaluar",
        json={**CREDITO, "tasa": 2.1175},
    )
    assert ok.status_code == 200


def test_evaluar_usura_bajo_monto(client):
    """A 5M (≤ 6 SMMLV) rige la usura de bajo monto (4,3488% m.v.),
    que permite tasas por encima de la ordinaria."""
    id_solicitud = _crear_solicitud(client)
    ok = client.post(
        f"/api/solicitudes/{id_solicitud}/evaluar",
        json={**CREDITO, "saldo_financiar": 5_000_000, "tasa": 3.5},
    )
    assert ok.status_code == 200

    r = client.post(
        f"/api/solicitudes/{id_solicitud}/evaluar",
        json={**CREDITO, "saldo_financiar": 5_000_000, "tasa": 5},
    )
    assert r.status_code == 422
    assert "usura" in r.json()["detail"].lower()


def test_simit_con_deuda_rechaza_sin_buro(client):
    """Pre-filtro: con deuda SIMIT la evaluación rechaza con R22 y la
    trazabilidad muestra que el buró nunca se consultó."""
    r = client.post("/api/motor/evaluar", json={**PAYLOAD, "escenario_mock": "simit_multas"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["decision"] == "Rechazado"
    assert [c["codigo"] for c in data["causales"]] == ["R22"]
    etapa = data["trazabilidad"][0]
    assert etapa["etapa"] == "Pre-filtro SIMIT"
    assert "no se consumió" in etapa["detalle"][0]
    # Sin buró no hay score ni indicadores.
    assert data["score_consultado"] is None
    assert data["indicadores_buro"] == {}


def test_simit_rechazo_tambien_en_solicitud_persistida(client):
    id_solicitud = _crear_solicitud(client)
    r = client.post(
        f"/api/solicitudes/{id_solicitud}/evaluar",
        json={**CREDITO, "escenario_mock": "simit_multas"},
    )
    assert r.status_code == 200 and r.json()["decision"] == "Rechazado"
    db = db_session.SessionLocal()
    try:
        solicitud = db.query(SolicitudCredito).one()
        assert solicitud.decision == "rechazado"
        assert [(c.codigo, c.activa) for c in db.query(SolicitudCausal)] == [("R22", True)]
    finally:
        db.close()


def test_simit_limpio_no_altera_el_flujo(client):
    """Paz y salvo (mock por defecto): la evaluación sigue al buró."""
    data = client.post("/api/motor/evaluar", json=PAYLOAD).json()
    assert data["decision"] == "Aprobado"
    assert data["trazabilidad"][0]["etapa"] != "Pre-filtro SIMIT"


def test_multas_declaradas_rechazan_sin_ninguna_consulta(client):
    """Si el propio cliente declaró multas, ni SIMIT ni buró se
    consultan: rechazo directo con la misma causal."""
    r = client.post(
        "/api/motor/evaluar", json={**PAYLOAD, "tiene_multas_runt": True}
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["decision"] == "Rechazado"
    assert [c["codigo"] for c in data["causales"]] == ["R22"]
    assert data["score_consultado"] is None
    assert "declaró" in data["trazabilidad"][0]["detalle"][0]


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
    # La oferta responde a lo pedido ($10M), no al cupo máximo del
    # motor ($20M): ese exceso de capacidad queda como cupo_sugerido.
    cupo = float(elegible["monto_aprobado"])
    assert cupo == 10_000_000

    # Monto por encima de la capacidad evaluada ($20M) -> 422
    r = client.post(
        f"/api/solicitudes/{id_solicitud}/ofertas/seleccionar",
        json={"id_oferta": elegible["id_oferta"], "monto": 20_000_001},
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


def test_oferta_vigencia_y_expiracion(client):
    """La oferta se genera con fecha_vigencia futura; si ya venció, la
    selección responde 409 y la API la reporta como expirada."""
    db = db_session.SessionLocal()
    aliado = AliadoFinanciero(nit="900000002", nombre="Aliado Vigencia", tipo="banco")
    db.add(aliado)
    db.flush()
    db.add(AliadoProducto(id_aliado=aliado.id_aliado, nombre="Producto A"))
    db.commit()
    db.close()

    id_solicitud = _crear_solicitud(client)
    assert client.post(f"/api/solicitudes/{id_solicitud}/evaluar", json=CREDITO).json()["decision"] == "Aprobado"
    ofertas = client.get(f"/api/solicitudes/{id_solicitud}/ofertas").json()
    elegible = next(o for o in ofertas if o["elegible"])
    assert elegible["fecha_vigencia"] is not None and elegible["expirada"] is False

    db = db_session.SessionLocal()
    oferta = db.query(OfertaCredito).filter_by(id_oferta=elegible["id_oferta"]).one()
    oferta.fecha_vigencia = datetime.now(UTC) - timedelta(days=1)
    db.commit()
    db.close()

    expirada = next(
        o for o in client.get(f"/api/solicitudes/{id_solicitud}/ofertas").json()
        if o["id_oferta"] == elegible["id_oferta"]
    )
    assert expirada["expirada"] is True
    r = client.post(
        f"/api/solicitudes/{id_solicitud}/ofertas/seleccionar",
        json={"id_oferta": elegible["id_oferta"]},
    )
    assert r.status_code == 409


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


def test_metricas_embudo(client):
    """D181: el embudo cuenta radicadas → evaluadas → aprobadas →
    formalizadas → desembolsadas, con desglose por aliado."""
    db = db_session.SessionLocal()
    aliado = AliadoFinanciero(nit="900000009", nombre="Aliado Embudo", tipo="banco")
    db.add(aliado)
    db.flush()
    db.add(AliadoProducto(id_aliado=aliado.id_aliado, nombre="Producto Embudo"))
    db.commit()
    db.close()

    aprobada = _crear_solicitud(client)
    client.post(f"/api/solicitudes/{aprobada}/evaluar", json=CREDITO)
    ofertas = client.get(f"/api/solicitudes/{aprobada}/ofertas").json()
    elegible = next(o for o in ofertas if o["elegible"])
    client.post(
        f"/api/solicitudes/{aprobada}/ofertas/seleccionar",
        json={"id_oferta": elegible["id_oferta"]},
    )

    rechazada = _crear_solicitud(client)
    client.post(
        f"/api/solicitudes/{rechazada}/evaluar",
        json={**CREDITO, "escenario_mock": "embargo"},
    )
    _crear_solicitud(client)  # solo radicada, sin evaluar

    db = db_session.SessionLocal()
    fila = db.query(SolicitudCredito).filter_by(id_solicitud=uuid.UUID(aprobada)).one()
    fila.fecha_hora_firma = datetime.now(UTC)
    fila.estado = "desembolsada"
    db.commit()
    db.close()

    data = client.get("/api/solicitudes/metricas/embudo").json()
    etapas = {e["clave"]: e for e in data["etapas"]}
    assert data["radicadas"] == 3
    assert etapas["evaluadas"]["total"] == 2
    assert etapas["aprobadas"]["total"] == 1
    assert etapas["formalizadas"]["total"] == 1
    assert etapas["desembolsadas"]["total"] == 1
    assert etapas["desembolsadas"]["pct"] == pytest.approx(33.3)
    assert data["canceladas"] == 0
    assert data["por_estado"]["desembolsada"] == 1
    assert data["por_estado"]["rechazada"] == 1
    [aliado] = data["por_aliado"]
    assert aliado["con_oferta"] == 1
    assert aliado["formalizadas"] == 1
    assert aliado["desembolsadas"] == 1
    assert Decimal(str(aliado["valor_desembolsado"])) == 0


def test_metricas_embudo_vacio(client):
    """Sin solicitudes el embudo responde ceros, nunca divide por cero."""
    data = client.get("/api/solicitudes/metricas/embudo").json()
    assert data["radicadas"] == 0
    assert all(e["total"] == 0 for e in data["etapas"])
    assert data["por_aliado"] == []


def test_metricas_embudo_rango(client):
    """El filtro de mes del panel acota el embudo por fecha de
    radicación: fuera del rango no cuenta."""
    _crear_solicitud(client)
    db = db_session.SessionLocal()
    vieja = db.query(SolicitudCredito).first()
    vieja.fecha_hora = datetime(2020, 1, 15, tzinfo=UTC)
    db.commit()
    db.close()
    _crear_solicitud(client)  # radicada hoy

    global_ = client.get("/api/solicitudes/metricas/embudo").json()
    assert global_["radicadas"] == 2
    # Rango del mes actual: solo la radicada hoy entra.
    ahora = datetime.now(UTC)
    desde = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    mes = client.get(
        "/api/solicitudes/metricas/embudo",
        params={"desde": desde.isoformat()},
    ).json()
    assert mes["radicadas"] == 1
    # Rango de 2020: solo la vieja entra.
    enero2020 = client.get(
        "/api/solicitudes/metricas/embudo",
        params={
            "desde": "2020-01-01T00:00:00Z",
            "hasta": "2020-02-01T00:00:00Z",
        },
    ).json()
    assert enero2020["radicadas"] == 1


def test_detalle_solicitud(client):
    id_solicitud = _crear_solicitud(client)
    client.post(
        f"/api/solicitudes/{id_solicitud}/evaluar",
        json={**CREDITO, "escenario_mock": "embargo"},
    )
    d = client.get(f"/api/solicitudes/{id_solicitud}").json()
    assert d["id_solicitud"] == id_solicitud
    assert d["nombre_cliente"] == "Cliente Ficticio"
    assert d["fecha_nacimiento"] == "1990-05-15"
    assert d["datos_laborales"]["ingreso_mensual"] == "5000000.00"
    assert d["datos_laborales"]["tipo_contrato"] == "indefinido"
    assert [c["codigo"] for c in d["causales"]] == ["R2"]
    assert d["evaluacion"]["decision_interna"] == "Rechazado"
    assert d["ofertas"] == []
    assert (
        client.get("/api/solicitudes/00000000-0000-0000-0000-000000000000").status_code
        == 404
    )


def test_actualizar_solicitud_completa_datos_sin_duplicar(client):
    """Retomar una solicitud creada con pasos pendientes (sin Habeas
    Data, sin contacto, perfil incompleto) persiste los datos sobre el
    mismo registro: el flujo de "continuar" no puede duplicarla."""
    id_solicitud = _crear_solicitud(client)

    r = client.put(
        f"/api/solicitudes/{id_solicitud}",
        json={
            **SOLICITUD,
            "datos_laborales": {
                "tipo_contrato": "Indefinido",
                "ingreso_mensual": 7200000,
                "meses_continuidad": 18,
            },
            "contacto_vivienda": {
                "telefono": "3001234567",
                "correo": "c@correo.com",
            },
            "consentimiento": {"aceptado": True},
            "linea_credito": "Inversiones Pacífico",
            "destino_credito": "Financiamiento de Vehículos",
            "plazo_deseado_meses": 36,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["id_solicitud"] == id_solicitud

    d = client.get(f"/api/solicitudes/{id_solicitud}").json()
    assert d["datos_laborales"]["ingreso_mensual"] == "7200000.00"
    assert d["datos_laborales"]["meses_continuidad"] == 18
    assert d["contacto_vivienda"]["telefono"] == "3001234567"
    assert d["linea_credito"] == "Inversiones Pacífico"
    assert d["plazo_deseado_meses"] == 36
    assert len(d["consentimientos"]) == 1
    # Sigue siendo una sola solicitud: no hubo radicación duplicada.
    assert len(client.get("/api/solicitudes").json()) == 1


def test_actualizar_solicitud_recrea_datos_laborales_faltantes(client):
    """Si la radicación quedó sin fila de datos_laborales (perfil
    económico pendiente), la actualización la crea como upsert."""
    id_solicitud = _crear_solicitud(client)
    db = db_session.SessionLocal()
    try:
        from backend.db_models.models import DatosLaborales

        db.query(DatosLaborales).filter_by(id_solicitud=uuid.UUID(id_solicitud)).delete()
        db.commit()
    finally:
        db.close()

    r = client.put(
        f"/api/solicitudes/{id_solicitud}",
        json={
            **SOLICITUD,
            "datos_laborales": {"tipo_contrato": "Indefinido", "ingreso_mensual": 4100000},
        },
    )
    assert r.status_code == 200, r.text
    assert client.get(f"/api/solicitudes/{id_solicitud}").json()["datos_laborales"][
        "ingreso_mensual"
    ] == "4100000.00"


def test_actualizar_solicitud_enlaza_sesion_captura(client):
    """Al retomar en el paso de evidencia, el token de la sesión nueva
    enlaza las fotos de la cédula a la solicitud existente."""
    import io

    sesion = client.post("/api/sesiones-captura").json()
    client.post(
        f"/api/captura/{sesion['token']}/evidencias",
        data={"tipo": "cedula_frontal"},
        files={"archivo": ("cedula.jpg", io.BytesIO(b"\xff\xd8\xff\xe0" + b"0" * 100), "image/jpeg")},
    )
    id_solicitud = _crear_solicitud(client)

    r = client.put(
        f"/api/solicitudes/{id_solicitud}",
        json={**SOLICITUD, "sesion_captura": sesion["token"]},
    )
    assert r.status_code == 200, r.text
    evidencias = client.get(f"/api/solicitudes/{id_solicitud}/evidencias").json()
    assert [e["tipo"] for e in evidencias] == ["cedula_frontal"]


def test_actualizar_solicitud_evaluada_rechaza(client):
    """Una solicitud con decisión ya no se re-diligencia por esta vía:
    la reevaluación administra su propio camino."""
    id_solicitud = _crear_solicitud(client)
    client.post(f"/api/solicitudes/{id_solicitud}/evaluar", json=CREDITO)

    r = client.put(f"/api/solicitudes/{id_solicitud}", json=SOLICITUD)
    assert r.status_code == 409


def test_actualizar_solicitud_rechazada_permite_rectificar(client):
    """Una rechazada sí se re-diligencia: corregir un dato mal capturado
    (p. ej. la ocupación) y re-evaluar es la ruta de recuperación.
    El resultado queda como una nueva versión de evaluación auditada."""
    id_solicitud = _crear_solicitud(client)
    client.post(
        f"/api/solicitudes/{id_solicitud}/evaluar",
        json={**CREDITO, "escenario_mock": "embargo"},
    )
    assert client.get(f"/api/solicitudes/{id_solicitud}").json()["decision"] == "rechazado"

    # Rectifica la ocupación: empleado -> pensionado sobre el mismo registro.
    r = client.put(
        f"/api/solicitudes/{id_solicitud}",
        json={**SOLICITUD, "cliente": {**SOLICITUD["cliente"], "ocupacion": "Pensionado"}},
    )
    assert r.status_code == 200, r.text
    assert client.get(f"/api/solicitudes/{id_solicitud}").json()["ocupacion"] == "pensionado"

    # Re-evalúa con los datos corregidos: nueva versión vigente.
    ev = client.post(f"/api/solicitudes/{id_solicitud}/evaluar", json=CREDITO)
    assert ev.status_code == 200, ev.text
    assert len(client.get("/api/auditoria", params={"numero_id": "1000000001"}).json()) == 2


def test_evaluar_genera_documentos_de_radicacion(client, tmp_path, monkeypatch):
    """La radicación deja soporte documental aunque el crédito no se
    concrete: la autorización de consulta a centrales (respaldo del
    consentimiento Habeas Data) y la solicitud de crédito diligenciada.
    Se generan para cualquier decisión — también para la rechazada."""
    from backend.config import get_settings

    monkeypatch.setenv("EVIDENCIAS_DIR", str(tmp_path / "evid"))
    get_settings.cache_clear()
    id_solicitud = _crear_solicitud(client)

    r = client.post(
        f"/api/solicitudes/{id_solicitud}/evaluar",
        json={**CREDITO, "escenario_mock": "embargo"},
    )
    assert r.status_code == 200 and r.json()["decision"] == "Rechazado"

    db = db_session.SessionLocal()
    try:
        docs = db.query(DocumentoEvidencia).all()
        assert {d.tipo for d in docs} == {"doc_autorizacion", "doc_solicitud"}
        for d in docs:
            assert (tmp_path / "evid" / d.ruta).exists(), d.tipo
            assert d.hash_sha256
    finally:
        db.close()


def test_actualizar_solicitud_inexistente(client):
    r = client.put(
        "/api/solicitudes/00000000-0000-0000-0000-000000000000", json=SOLICITUD
    )
    assert r.status_code == 404


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


def test_tasa_mercado(client):
    """GET /api/tasa-mercado expone el TIBC de la SFC convertido a m.v."""
    from backend.main import app
    from backend.routes.dependencies import get_tasa_mercado_service
    from backend.services.tasa_mercado_service import TasaMercadoService

    filas = [
        {
            "resolucion": "1472",
            "vigencia_desde": "2026-10-01T00:00:00.000",
            "vigencia_hasta": "2026-10-31T00:00:00.000",
            "interes_bancario_corriente": "44.44%",
            "modalidad": "CONSUMO BAJO MONTO",
        },
        {
            "resolucion": "1472",
            "vigencia_desde": "2026-10-01T00:00:00.000",
            "vigencia_hasta": "2026-10-31T00:00:00.000",
            "interes_bancario_corriente": "19.06%",
            "modalidad": "CONSUMO Y ORDINARIO",
        },
    ]

    class ClienteFalso:
        def tasas_vigentes(self, modalidades):
            return filas

    class SettingsFalso:
        smmlv = 1_300_000  # igual que el fixture del conftest
        sfc_tasas_cache_segundos = 21_600.0

    app.dependency_overrides[get_tasa_mercado_service] = (
        lambda: TasaMercadoService(ClienteFalso(), SettingsFalso())
    )
    try:
        r = client.get("/api/tasa-mercado")
    finally:
        app.dependency_overrides.pop(get_tasa_mercado_service, None)

    assert r.status_code == 200
    datos = r.json()
    assert datos["umbral_bajo_monto"] == 6 * 1_300_000
    bajo = datos["bajo_monto"]
    assert bajo["modalidad"] == "CONSUMO BAJO MONTO"
    assert bajo["tasa_ea"] == pytest.approx(44.44)
    assert bajo["tasa_mv"] == pytest.approx(3.1115, abs=0.001)
    assert bajo["usura_ea"] == pytest.approx(66.66)
    assert bajo["vigencia_hasta"] == "2026-10-31"
    assert datos["ordinario"]["tasa_ea"] == pytest.approx(19.06)
    assert "datos.gov.co" in datos["fuente"]


def test_tasa_mercado_fuente_caida_devuelve_502(client):
    from backend.main import app
    from backend.routes.dependencies import get_tasa_mercado_service
    from backend.services.motor_exceptions import DataCreditoError
    from backend.services.tasa_mercado_service import TasaMercadoService

    class ClienteCaido:
        def tasas_vigentes(self, modalidades):
            raise DataCreditoError("sfc_tasas", 500, "caído")

    class SettingsFalso:
        smmlv = 1_300_000
        sfc_tasas_cache_segundos = 21_600.0

    app.dependency_overrides[get_tasa_mercado_service] = (
        lambda: TasaMercadoService(ClienteCaido(), SettingsFalso())
    )
    try:
        r = client.get("/api/tasa-mercado")
    finally:
        app.dependency_overrides.pop(get_tasa_mercado_service, None)
    assert r.status_code == 502


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
    assert d["capital"] == "10000000.00"  # saldo_financiar pedido (cupo era $20M)
    assert d["plazo"] == 36 and d["tasa"] == "2.0000"
    assert d["referencia_pago"] == "TRX-TEST-1"
    assert d["fecha_desembolso"] is not None

    assert client.get(f"/api/solicitudes/{id_solicitud}").json()["estado"] == "desembolsada"

    db = db_session.SessionLocal()
    try:
        credito = db.query(CreditoFinanciacion).one()
        assert credito.ganadora is True
        assert credito.valor_financiacion == 10000000
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


def test_desembolso_desglosa_seguro_vida(client):
    """Con el catálogo de seguros sembrado, la oferta trae la cuota
    TOTAL y el crédito la desglosa: anualidad + prima mensual."""
    db = db_session.SessionLocal()
    _sembrar_cadena_desembolso(db)
    aseguradora = Aseguradora(nit="999999999", nombre="Aseguradora Test")
    db.add(aseguradora)
    db.flush()
    db.add(
        SeguroProducto(
            id_aseguradora=aseguradora.id_aseguradora,
            tipo="vida_decreciente",
            nombre="Vida deudores",
            tasa_prima=0.35,
            activo=True,
        )
    )
    db.commit()
    db.close()

    id_solicitud = _solicitud_aprobada_con_oferta(client)
    r = client.post(f"/api/solicitudes/{id_solicitud}/desembolso", json=DESEMBOLSO)
    assert r.status_code == 201, r.text

    db = db_session.SessionLocal()
    try:
        credito = db.query(CreditoFinanciacion).one()
        # cupo 20.000.000 al 2 % a 36 meses → anualidad + 0,22 %/mes
        assert float(credito.cuota_seguro_vida) > 0
        assert abs(
            float(credito.cuota_total)
            - (float(credito.cuota_financiacion) + float(credito.cuota_seguro_vida))
        ) < 1
        assert float(credito.valor_seguro_vida) == pytest.approx(
            float(credito.cuota_seguro_vida) * credito.plazo, abs=1
        )
        assert credito.dia_pago == 20
        desembolso = db.query(Desembolso).one()
        assert float(desembolso.valor_seguro) > 0
    finally:
        db.close()


# ---------------------------------------------------------------------------
# OTP: emisión, verificación y firma del pagaré
# ---------------------------------------------------------------------------
def test_otp_generar_envia_correo_demo(client):
    """En modo demo el código viaja en la respuesta (sin proveedor externo)."""
    id_solicitud = _crear_solicitud(client)
    r = client.post(f"/api/solicitudes/{id_solicitud}/otp", json={})
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["expira_en_segundos"] > 0
    assert cuerpo["codigo_demo"] is not None
    assert len(cuerpo["codigo_demo"]) == 6


def test_otp_verificar_firma_pagare(client):
    id_solicitud = _crear_solicitud(client)
    codigo = client.post(
        f"/api/solicitudes/{id_solicitud}/otp", json={}
    ).json()["codigo_demo"]
    r = client.post(
        f"/api/solicitudes/{id_solicitud}/otp/verificar",
        json={"accion": "firma_pagare", "codigo": codigo},
    )
    assert r.status_code == 200, r.text
    assert r.json()["verificado"] is True
    assert r.json()["uuid_firma"]
    # El OTP ya usado no se puede reutilizar.
    assert (
        client.post(
            f"/api/solicitudes/{id_solicitud}/otp/verificar",
            json={"accion": "firma_pagare", "codigo": codigo},
        ).status_code
        == 422
    )


def test_consentimiento_habeas_data(client):
    """El consentimiento del paso 2 y el de la firma OTP quedan
    persistidos con versión de texto, hash SHA-256, canal e IP."""
    r = client.post(
        "/api/solicitudes",
        json={**SOLICITUD, "consentimiento": {"aceptado": True}},
    )
    assert r.status_code == 201, r.text
    id_solicitud = r.json()["id_solicitud"]

    detalle = client.get(f"/api/solicitudes/{id_solicitud}").json()
    assert len(detalle["consentimientos"]) == 1
    web = detalle["consentimientos"][0]
    assert web["canal"] == "web_asesor"
    assert web["version_texto"] == "v1"
    assert len(web["hash_texto"]) == 64 and web["ip"]
    # La fecha de aceptación lleva hora exacta (ISO con hh:mm:ss).
    assert "T" in web["fecha_aceptacion"] and ":" in web["fecha_aceptacion"]

    codigo = client.post(
        f"/api/solicitudes/{id_solicitud}/otp", json={}
    ).json()["codigo_demo"]
    r = client.post(
        f"/api/solicitudes/{id_solicitud}/otp/verificar",
        json={"accion": "firma_pagare", "codigo": codigo},
    )
    assert r.status_code == 200, r.text
    canales = [
        c["canal"]
        for c in client.get(f"/api/solicitudes/{id_solicitud}").json()[
            "consentimientos"
        ]
    ]
    assert canales == ["web_asesor", "otp_firma"]


def test_cancelar_solicitud(client):
    """creada→cancelada con motivo (queda en descripcion_estado, que el
    trigger de Postgres copia al historial). Cancelada o desembolsada
    no se puede volver a cancelar → 409; sin motivo → 422."""
    id_solicitud = _crear_solicitud(client)
    r = client.post(
        f"/api/solicitudes/{id_solicitud}/cancelar",
        json={"motivo": "el cliente desistió del crédito"},
    )
    assert r.status_code == 200 and r.json()["estado"] == "cancelada"
    detalle = client.get(f"/api/solicitudes/{id_solicitud}").json()
    assert detalle["estado"] == "cancelada"
    assert "desistió" in (detalle["descripcion_estado"] or "")

    # Ya cancelada → conflicto
    r = client.post(
        f"/api/solicitudes/{id_solicitud}/cancelar",
        json={"motivo": "duplicada"},
    )
    assert r.status_code == 409

    # Desembolsada no se puede cancelar
    otra = _crear_solicitud(client)
    db = db_session.SessionLocal()
    db.query(SolicitudCredito).filter_by(id_solicitud=uuid.UUID(otra)).update(
        {"estado": "desembolsada"}
    )
    db.commit()
    db.close()
    r = client.post(
        f"/api/solicitudes/{otra}/cancelar",
        json={"motivo": "error de digitación"},
    )
    assert r.status_code == 409

    # Sin motivo válido → 422; inexistente → 404
    assert (
        client.post(
            f"/api/solicitudes/{otra}/cancelar", json={"motivo": "x"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/solicitudes/00000000-0000-0000-0000-000000000000/cancelar",
            json={"motivo": "no existe"},
        ).status_code
        == 404
    )


def test_otp_codigo_incorrecto_y_renovacion(client):
    id_solicitud = _crear_solicitud(client)
    r = client.post(
        f"/api/solicitudes/{id_solicitud}/otp/verificar",
        json={"accion": "firma_pagare", "codigo": "000000"},
    )
    assert r.status_code == 422
    client.post(f"/api/solicitudes/{id_solicitud}/otp", json={})
    malo = client.post(
        f"/api/solicitudes/{id_solicitud}/otp/verificar",
        json={"accion": "firma_pagare", "codigo": "999999"},
    )
    assert malo.status_code == 422
    # Generar uno nuevo invalida el pendiente anterior.
    codigo = client.post(
        f"/api/solicitudes/{id_solicitud}/otp", json={}
    ).json()["codigo_demo"]
    assert (
        client.post(
            f"/api/solicitudes/{id_solicitud}/otp/verificar",
            json={"accion": "firma_pagare", "codigo": codigo},
        ).status_code
        == 200
    )


def test_otp_whatsapp_simulado_y_firma(client):
    """Sin credenciales WATI el canal whatsapp queda 'simulado' (log) y
    la firma se sella como otp_whatsapp."""
    r = client.post(
        "/api/solicitudes",
        json={
            **SOLICITUD,
            "contacto_vivienda": {"telefono": "300 123 4567"},
        },
    )
    assert r.status_code == 201, r.text
    id_solicitud = r.json()["id_solicitud"]

    r = client.post(
        f"/api/solicitudes/{id_solicitud}/otp",
        json={"canal": "whatsapp"},
    )
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["canal"] == "whatsapp"
    assert cuerpo["estado_envio"] == "simulado"
    assert cuerpo["destino"] == "573001234567"

    codigo = cuerpo["codigo_demo"]
    assert (
        client.post(
            f"/api/solicitudes/{id_solicitud}/otp/verificar",
            json={"accion": "firma_pagare", "codigo": codigo},
        ).status_code
        == 200
    )
    db = db_session.SessionLocal()
    try:
        solicitud = db.query(SolicitudCredito).filter_by(
            id_solicitud=uuid.UUID(id_solicitud)
        ).one()
        assert solicitud.autenticacion == "otp_whatsapp"
    finally:
        db.close()


def test_otp_whatsapp_cae_a_email_sin_telefono(client):
    """canal=whatsapp sin teléfono válido cae al correo del cliente."""
    r = client.post(
        "/api/solicitudes",
        json={
            **SOLICITUD,
            "contacto_vivienda": {"correo": "cliente@correo.co"},
        },
    )
    id_solicitud = r.json()["id_solicitud"]
    cuerpo = client.post(
        f"/api/solicitudes/{id_solicitud}/otp",
        json={"canal": "whatsapp"},
    ).json()
    assert cuerpo["canal"] == "email"
    assert cuerpo["destino"] == "cliente@correo.co"


def test_otp_canal_email_explicito_y_por_defecto(client):
    """canal='email' va directo al correo; sin canal se asume whatsapp y
    sin teléfono cae a email (sin_destino si tampoco hay correo)."""
    r = client.post(
        "/api/solicitudes",
        json={
            **SOLICITUD,
            "contacto_vivienda": {"correo": "cliente@correo.co"},
        },
    )
    id_solicitud = r.json()["id_solicitud"]
    cuerpo = client.post(
        f"/api/solicitudes/{id_solicitud}/otp", json={"canal": "email"}
    ).json()
    assert cuerpo["canal"] == "email"
    assert cuerpo["destino"] == "cliente@correo.co"

    # Solicitud sin contacto: whatsapp→email→sin_destino.
    id_solicitud = _crear_solicitud(client)
    cuerpo = client.post(
        f"/api/solicitudes/{id_solicitud}/otp", json={}
    ).json()
    assert cuerpo["canal"] == "email"
    assert cuerpo["estado_envio"] == "sin_destino"


# ---------------------------------------------------------------------------
# Datos de formalización (información del cliente antes del OTP)
# ---------------------------------------------------------------------------
def test_datos_formalizacion_guarda_y_expone(client):
    id_solicitud = _crear_solicitud(client)
    payload = {
        "via_principal": "Calle",
        "numero_via": "48",
        "letra_via": "A",
        "sector": "Norte",
        "numero_cruce": "101",
        "letra_cruce": "B",
        "numero_final": "40",
        "otras_caracteristicas": "Casa 10",
        "barrio": "La Flora",
        "ciudad": "Cali, Valle del Cauca",
        "estrato": 4,
        "tipo_vivienda": "Arrendada",
        "zona_rural": False,
        "estado_civil": "Casado(a)",
        "personas_a_cargo": 3,
        "num_hijos": 2,
        "es_cabeza_familia": True,
        "cuenta_bienes_raices": True,
        "cuenta_vehiculo": True,
        "tiene_moto": True,
        "tiene_carro": False,
        "primera_moto": False,
        "estoy_financiando": True,
        "nombre_empresa": "Distribuciones ABC",
        "ciudad_empresa": "Palmira, Valle del Cauca",
        "fecha_ingreso": "2020-03-01",
        "nivel_educativo": "Profesional",
        "profesion": "Administrador",
        "cargo": "Auxiliar administrativo",
        "actividad_comercial": "Comercio",
    }
    r = client.put(f"/api/solicitudes/{id_solicitud}/datos-formalizacion", json=payload)
    assert r.status_code == 204, r.text

    detalle = client.get(f"/api/solicitudes/{id_solicitud}").json()
    contacto = detalle["contacto_vivienda"]
    assert contacto["direccion"] == "Calle 48 A Norte No. 101 B-40, Casa 10"
    assert contacto["barrio"] == "La Flora"
    assert contacto["ciudad"] == "Cali, Valle del Cauca"
    assert contacto["estrato"] == 4
    assert contacto["tipo_vivienda"] == "Arrendada"
    assert contacto["zona_rural"] is False
    assert contacto["estado_civil"] == "Casado(a)"
    assert contacto["personas_a_cargo"] == 3
    assert contacto["num_hijos"] == 2
    assert contacto["es_cabeza_familia"] is True
    assert contacto["cuenta_bienes_raices"] is True
    assert contacto["tiene_moto"] is True
    assert contacto["tiene_carro"] is False
    assert contacto["primera_moto"] is False
    assert contacto["estoy_financiando"] is True
    # Los canales capturados en originación no se tocan.
    assert contacto["correo"] is None and contacto["telefono"] is None

    laboral = detalle["datos_laborales"]
    assert laboral["nombre_empresa"] == "Distribuciones ABC"
    assert laboral["ciudad_empresa"] == "Palmira, Valle del Cauca"
    assert laboral["fecha_ingreso"] == "2020-03-01"
    assert laboral["nivel_educativo"] == "Profesional"
    assert laboral["profesion"] == "Administrador"
    assert laboral["cargo"] == "Auxiliar administrativo"
    assert laboral["actividad_comercial"] == "Comercio"


def test_datos_formalizacion_parcial_no_borra(client):
    """Un segundo PUT con pocos campos actualiza solo esos."""
    id_solicitud = _crear_solicitud(client)
    client.put(
        f"/api/solicitudes/{id_solicitud}/datos-formalizacion",
        json={"barrio": "Centro", "estado_civil": "Soltero(a)"},
    )
    client.put(
        f"/api/solicitudes/{id_solicitud}/datos-formalizacion",
        json={"num_hijos": 1},
    )
    detalle = client.get(f"/api/solicitudes/{id_solicitud}").json()
    contacto = detalle["contacto_vivienda"]
    assert contacto["barrio"] == "Centro"
    assert contacto["estado_civil"] == "Soltero(a)"
    assert contacto["num_hijos"] == 1


def test_datos_formalizacion_solicitud_inexistente(client):
    r = client.put(
        "/api/solicitudes/00000000-0000-0000-0000-000000000000/datos-formalizacion",
        json={"barrio": "Centro"},
    )
    assert r.status_code == 404


def test_crear_solicitud_persiste_nombre_empresa(client):
    """El empleador capturado en el paso 4 queda en datos_laborales para
    precargar el formulario de formalización."""
    solicitud = {
        **SOLICITUD,
        "cliente": {**SOLICITUD["cliente"], "num_cedula": "1000000099"},
        "datos_laborales": {
            **SOLICITUD["datos_laborales"],
            "nombre_empresa": "Empleador Precargado S.A.S.",
        },
    }
    r = client.post("/api/solicitudes", json=solicitud)
    assert r.status_code == 201, r.text
    detalle = client.get(f"/api/solicitudes/{r.json()['id_solicitud']}").json()
    assert detalle["datos_laborales"]["nombre_empresa"] == "Empleador Precargado S.A.S."
