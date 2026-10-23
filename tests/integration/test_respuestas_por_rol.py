"""Respuestas por rol: el asesor y el aliado reciben decisión y oferta,
nunca score, indicadores de buró, decisión interna ni causales."""

from tests.integration.conftest import _token_rol
from tests.integration.test_api import CREDITO, SOLICITUD

CAMPOS_INTERNOS = (
    "score_consultado",
    "score_tipo",
    "perfil_score",
    "perfil_ingreso",
    "decision_interna",
    "causales",
    "endeudamiento",
    "capacidad_pago",
    "indicadores_buro",
    "valor_ingreso_respuesta",
)


def _solicitud_con_evaluacion(client):
    id_solicitud = client.post("/api/solicitudes", json=SOLICITUD).json()["id_solicitud"]
    client.post(f"/api/solicitudes/{id_solicitud}/evaluar", json=CREDITO)
    return id_solicitud


def test_evaluar_admin_devuelve_detalle_completo(client):
    id_solicitud = _solicitud_con_evaluacion(client)
    resultado = client.post(
        f"/api/solicitudes/{id_solicitud}/evaluar", json=CREDITO
    ).json()
    assert resultado["decision"] is not None
    assert resultado["decision_interna"] is not None
    assert "indicadores_buro" in resultado


def test_evaluar_asesor_devuelve_vista_binaria(client_asesor):
    id_solicitud = client_asesor.post("/api/solicitudes", json=SOLICITUD).json()[
        "id_solicitud"
    ]
    resultado = client_asesor.post(
        f"/api/solicitudes/{id_solicitud}/evaluar", json=CREDITO
    ).json()
    # Sí recibe: decisión y capacidad de oferta.
    assert resultado["decision"] is not None
    # No recibe: nada interno.
    for campo in CAMPOS_INTERNOS:
        assert resultado.get(campo) in (None, [], {}), campo


def test_detalle_admin_incluye_score_y_causales(client):
    id_solicitud = _solicitud_con_evaluacion(client)
    detalle = client.get(f"/api/solicitudes/{id_solicitud}").json()
    assert detalle["evaluacion"]["score"] is not None
    assert detalle["evaluacion"]["decision_interna"] is not None
    assert "causales" in detalle


def test_detalle_asesor_oculta_score_y_causales(client_asesor):
    id_solicitud = client_asesor.post("/api/solicitudes", json=SOLICITUD).json()[
        "id_solicitud"
    ]
    client_asesor.post(f"/api/solicitudes/{id_solicitud}/evaluar", json=CREDITO)
    detalle = client_asesor.get(f"/api/solicitudes/{id_solicitud}").json()
    # Decisión y oferta sí visibles…
    assert detalle["decision"] is not None
    assert "ofertas" in detalle
    # …pero nada interno.
    assert detalle["causales"] == []
    ev = detalle["evaluacion"]
    assert ev["score"] is None
    assert ev["perfil_score"] is None
    assert ev["perfil_ingreso"] is None
    assert ev["decision_interna"] is None
    assert ev["endeudamiento"] is None
    assert ev["capacidad_pago"] is None
    # Lo que sostiene la oferta sí llega.
    assert ev["cupo_sugerido"] is not None


def test_listado_asesor_oculta_detalle_interno(client_asesor):
    client_asesor.post("/api/solicitudes", json=SOLICITUD)
    id_solicitud = client_asesor.get("/api/solicitudes").json()[0]["id_solicitud"]
    client_asesor.post(f"/api/solicitudes/{id_solicitud}/evaluar", json=CREDITO)
    fila = next(
        s
        for s in client_asesor.get("/api/solicitudes").json()
        if s["id_solicitud"] == id_solicitud
    )
    if fila["evaluacion"] is not None:
        assert fila["evaluacion"]["score"] is None
        assert fila["evaluacion"]["decision_interna"] is None


def test_detalle_aliado_tambien_binario(client_asesor, client_aliado):
    """El aliado comparte la sede del asesor de prueba: ve la solicitud,
    pero igualmente saneada."""
    id_solicitud = client_asesor.post("/api/solicitudes", json=SOLICITUD).json()[
        "id_solicitud"
    ]
    client_asesor.post(f"/api/solicitudes/{id_solicitud}/evaluar", json=CREDITO)
    detalle = client_aliado.get(f"/api/solicitudes/{id_solicitud}").json()
    assert detalle["causales"] == []
    assert detalle["evaluacion"]["score"] is None
