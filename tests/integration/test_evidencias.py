"""Captura remota de evidencias: sesión con token, subida y enlace a solicitud (D161)."""

import io

from tests.integration.test_api import SOLICITUD


def _crear_sesion(client) -> dict:
    r = client.post("/api/sesiones-captura")
    assert r.status_code == 201, r.text
    return r.json()


def test_flujo_captura_completo(client):
    sesion = _crear_sesion(client)
    token = sesion["token"]

    estado = client.get(f"/api/captura/{token}").json()
    assert estado["estado"] == "pendiente"
    assert set(estado["pendientes"]) == {
        "cedula_frontal",
        "cedula_reverso",
        "video_prueba_vida",
    }

    jpeg = b"\xff\xd8\xff\xe0" + b"0" * 100  # contenido simulado mínimo
    r = client.post(
        f"/api/captura/{token}/evidencias",
        data={"tipo": "cedula_frontal"},
        files={"archivo": ("cedula.jpg", io.BytesIO(jpeg), "image/jpeg")},
    )
    assert r.status_code == 201, r.text
    assert r.json()["hash_sha256"]

    client.post(
        f"/api/captura/{token}/evidencias",
        data={"tipo": "cedula_reverso"},
        files={"archivo": ("reverso.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"1" * 50), "image/png")},
    )
    client.post(
        f"/api/captura/{token}/evidencias",
        data={"tipo": "video_prueba_vida"},
        files={"archivo": ("video.webm", io.BytesIO(b"\x1a\x45\xdf\xa3" + b"2" * 50), "video/webm")},
    )

    completa = client.get(f"/api/captura/{token}").json()
    assert completa["estado"] == "completada"
    assert completa["pendientes"] == []

    # La sesión se enlaza al crear la solicitud con el token.
    r = client.post(
        "/api/solicitudes",
        json={**SOLICITUD, "cliente": {**SOLICITUD["cliente"], "num_cedula": "555000111"}, "sesion_captura": token},
    )
    assert r.status_code == 201, r.text
    evidencias = client.get(f"/api/solicitudes/{r.json()['id_solicitud']}/evidencias").json()
    assert {e["tipo"] for e in evidencias} == {
        "cedula_frontal",
        "cedula_reverso",
        "video_prueba_vida",
    }

    # El archivo es descargable por el asesor.
    contenido = client.get(f"/api/evidencias/{evidencias[0]['id_evidencia']}/contenido")
    assert contenido.status_code == 200


def test_captura_token_invalido(client):
    assert client.get("/api/captura/no-existe").status_code == 404
    assert (
        client.post(
            "/api/captura/no-existe/evidencias",
            data={"tipo": "cedula_frontal"},
            files={"archivo": ("x.jpg", io.BytesIO(b"xx"), "image/jpeg")},
        ).status_code
        == 404
    )


def test_captura_rechaza_tipo_y_mime(client):
    token = _crear_sesion(client)["token"]
    assert (
        client.post(
            f"/api/captura/{token}/evidencias",
            data={"tipo": "inventado"},
            files={"archivo": ("x.jpg", io.BytesIO(b"xx"), "image/jpeg")},
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/captura/{token}/evidencias",
            data={"tipo": "cedula_frontal"},
            files={"archivo": ("x.txt", io.BytesIO(b"hola"), "text/plain")},
        ).status_code
        == 422
    )


def test_captura_reemite_reemplazando_evidencia(client):
    token = _crear_sesion(client)["token"]
    for i in range(2):
        client.post(
            f"/api/captura/{token}/evidencias",
            data={"tipo": "cedula_frontal"},
            files={"archivo": (f"c{i}.jpg", io.BytesIO(b"\xff\xd8\xff" + bytes([i]) * 30), "image/jpeg")},
        )
    estado = client.get(f"/api/captura/{token}").json()
    frontales = [e for e in estado["evidencias"] if e["tipo"] == "cedula_frontal"]
    assert len(frontales) == 1
