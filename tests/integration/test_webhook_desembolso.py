"""Webhook POST /webhook/desembolso: firma HMAC, anti-replay e
idempotencia sobre la confirmación asíncrona del giro."""

import hashlib
import hmac
import json
import time

import pytest

from backend.config import get_settings
from backend.db_models import session as db_session
from backend.db_models.models import Desembolso
from tests.integration.test_api import (
    CREDITO,
    SOLICITUD,
    _sembrar_cadena_desembolso,
)

SECRETO = "secreto-webhook-pruebas"

CUERPO_BASE = {
    "estado": "confirmado",
    "codigo_ach_banco": "007",
    "numero_cuenta_cliente": "12345678901",
    "titular_cuenta": "Cliente Ficticio",
    "referencia_pago": "TRX-WEBHOOK-1",
    "id_evento": "EVT-001",
}


def _firmar(body: bytes, secreto: str = SECRETO, ts: int | None = None) -> dict:
    ts = int(time.time()) if ts is None else ts
    firma = hmac.new(
        secreto.encode(), f"{ts}.".encode() + body, hashlib.sha256
    ).hexdigest()
    return {"X-Signature": f"sha256={firma}", "X-Timestamp": str(ts)}


def _post(client, payload: dict, headers: dict | None = None):
    body = json.dumps(payload).encode()
    return client.post("/webhook/desembolso", content=body, headers=headers or _firmar(body))


@pytest.fixture(autouse=True)
def secreto_webhook(client):
    # Depende de `client` para correr DESPUÉS de su cache_clear(): si
    # mutara antes, get_settings() en la ruta devolvería una instancia
    # nueva con el secreto vacío.
    settings = get_settings()
    anterior = settings.webhook_secreto
    settings.webhook_secreto = SECRETO
    yield
    settings.webhook_secreto = anterior


def _solicitud_aprobada_con_oferta(client) -> str:
    r = client.post("/api/solicitudes", json=SOLICITUD)
    assert r.status_code == 201, r.text
    id_solicitud = r.json()["id_solicitud"]
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


def test_webhook_confirma_desembolso(client):
    db = db_session.SessionLocal()
    _sembrar_cadena_desembolso(db)
    id_solicitud = _solicitud_aprobada_con_oferta(client)

    r = _post(client, {**CUERPO_BASE, "id_solicitud": id_solicitud})
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "confirmado"
    assert client.get(f"/api/solicitudes/{id_solicitud}").json()["estado"] == "desembolsada"
    db.close()


def test_webhook_idempotente(client):
    """El mismo evento reenviado devuelve el mismo desembolso."""
    db = db_session.SessionLocal()
    _sembrar_cadena_desembolso(db)
    id_solicitud = _solicitud_aprobada_con_oferta(client)

    r1 = _post(client, {**CUERPO_BASE, "id_solicitud": id_solicitud})
    r2 = _post(client, {**CUERPO_BASE, "id_solicitud": id_solicitud})
    assert r2.status_code == 200
    assert r2.json()["num_desembolso"] == r1.json()["num_desembolso"]
    db.close()


def test_webhook_identifica_por_num_solicitud(client):
    db = db_session.SessionLocal()
    _sembrar_cadena_desembolso(db)
    id_solicitud = _solicitud_aprobada_con_oferta(client)
    # num_solicitud es IDENTITY en Postgres; en SQLite queda NULL, así
    # que se asigna a mano para ejercer la identificación por número.
    import uuid

    from backend.db_models.models import SolicitudCredito

    s = (
        db.query(SolicitudCredito)
        .filter(SolicitudCredito.id_solicitud == uuid.UUID(id_solicitud))
        .one()
    )
    s.num_solicitud = 555
    db.commit()

    r = _post(client, {**CUERPO_BASE, "num_solicitud": 555})
    assert r.status_code == 200, r.text
    assert r.json()["id_solicitud"] == id_solicitud
    db.close()


def test_webhook_firma_invalida(client):
    db = db_session.SessionLocal()
    _sembrar_cadena_desembolso(db)
    id_solicitud = _solicitud_aprobada_con_oferta(client)

    body = json.dumps({**CUERPO_BASE, "id_solicitud": id_solicitud}).encode()
    r = client.post(
        "/webhook/desembolso",
        content=body,
        headers={
            "X-Signature": "sha256=" + "0" * 64,
            "X-Timestamp": str(int(time.time())),
        },
    )
    assert r.status_code == 401
    # Y no se confirmó nada.
    assert client.get(f"/api/solicitudes/{id_solicitud}").json()["estado"] != "desembolsada"
    db.close()


def test_webhook_timestamp_expirado(client):
    body = json.dumps({**CUERPO_BASE, "num_solicitud": 1}).encode()
    viejo = int(time.time()) - 3600
    r = client.post("/webhook/desembolso", content=body, headers=_firmar(body, ts=viejo))
    assert r.status_code == 401


def test_webhook_sin_headers(client):
    r = client.post("/webhook/desembolso", content=b"{}", headers={})
    assert r.status_code == 401


def test_webhook_sin_secreto_configurado(client):
    get_settings().webhook_secreto = ""
    body = json.dumps({**CUERPO_BASE, "num_solicitud": 1}).encode()
    r = client.post("/webhook/desembolso", content=body, headers=_firmar(body))
    assert r.status_code == 503


def test_webhook_solicitud_inexistente(client):
    r = _post(client, {**CUERPO_BASE, "num_solicitud": 99999})
    assert r.status_code == 404


def test_webhook_rechaza_desembolso_pendiente(client):
    db = db_session.SessionLocal()
    _sembrar_cadena_desembolso(db)
    id_solicitud = _solicitud_aprobada_con_oferta(client)

    # Formaliza el crédito con desembolso pendiente (como lo haría el
    # registro manual cuando la tesorería aún no gira).
    r = client.post(
        f"/api/solicitudes/{id_solicitud}/desembolso",
        json={
            "codigo_ach_banco": "007",
            "numero_cuenta_cliente": "12345678901",
        },
    )
    assert r.status_code == 201, r.text
    pendiente = db.query(Desembolso).one()
    pendiente.estado = "pendiente"
    db.commit()

    r = _post(
        client,
        {
            "id_solicitud": id_solicitud,
            "estado": "rechazado",
            "motivo": "Cuenta receptora bloqueada",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "rechazado"
    db.refresh(pendiente)
    assert pendiente.estado == "rechazado"
    db.close()


def test_webhook_en_transito_luego_confirmado(client):
    """Ciclo real del giro: el emisor anuncia la transferencia
    (desembolso pendiente, solicitud aún no desembolsada) y luego la
    confirma (desembolso confirmado, solicitud desembolsada)."""
    db = db_session.SessionLocal()
    _sembrar_cadena_desembolso(db)
    id_solicitud = _solicitud_aprobada_con_oferta(client)

    r = _post(
        client,
        {**CUERPO_BASE, "id_solicitud": id_solicitud, "estado": "en_transito"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "pendiente"
    pendiente = db.query(Desembolso).one()
    assert pendiente.estado == "pendiente" and pendiente.fecha_desembolso is None
    # La solicitud no se marca desembolsada hasta la confirmación real.
    assert client.get(f"/api/solicitudes/{id_solicitud}").json()["estado"] == "aprobada"

    r = _post(
        client,
        {**CUERPO_BASE, "id_solicitud": id_solicitud, "referencia_pago": "TRX-WEBHOOK-2"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "confirmado"
    assert r.json()["num_desembolso"] == pendiente.num_desembolso
    assert client.get(f"/api/solicitudes/{id_solicitud}").json()["estado"] == "desembolsada"
    db.close()


def test_webhook_en_transito_luego_rechazado(client):
    """Si el giro en tránsito falla en el emisor, el webhook lo marca
    rechazado sobre el mismo desembolso pendiente."""
    db = db_session.SessionLocal()
    _sembrar_cadena_desembolso(db)
    id_solicitud = _solicitud_aprobada_con_oferta(client)

    r = _post(
        client,
        {**CUERPO_BASE, "id_solicitud": id_solicitud, "estado": "en_transito"},
    )
    assert r.status_code == 200, r.text
    r = _post(
        client,
        {
            "id_solicitud": id_solicitud,
            "estado": "rechazado",
            "motivo": "Cuenta receptora bloqueada",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "rechazado"
    assert db.query(Desembolso).one().estado == "rechazado"
    db.close()


def test_webhook_rechazo_sin_desembolso_en_transito(client):
    db = db_session.SessionLocal()
    _sembrar_cadena_desembolso(db)
    id_solicitud = _solicitud_aprobada_con_oferta(client)
    r = _post(client, {"id_solicitud": id_solicitud, "estado": "rechazado"})
    assert r.status_code == 409
    db.close()
