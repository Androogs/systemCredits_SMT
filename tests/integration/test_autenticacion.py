"""Pruebas de inicio de sesión en el entorno demo."""


def test_login_demo_devuelve_usuario(client):
    respuesta = client.post(
        "/api/auth/login",
        json={"correo": "demo@underwriting.io", "contrasena": "demo1234"},
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "usuario": {
            "correo": "demo@underwriting.io",
            "nombre": "Usuario de demostración",
            "rol": "Administrador",
        }
    }


def test_login_demo_normaliza_correo(client):
    respuesta = client.post(
        "/api/auth/login",
        json={"correo": "  DEMO@UNDERWRITING.IO ", "contrasena": "demo1234"},
    )

    assert respuesta.status_code == 200


def test_login_rechaza_credenciales_incorrectas(client):
    respuesta = client.post(
        "/api/auth/login",
        json={"correo": "demo@underwriting.io", "contrasena": "incorrecta"},
    )

    assert respuesta.status_code == 401
    assert respuesta.json()["detail"] == "Correo o contraseña incorrectos."


def test_login_demo_no_se_habilita_en_produccion(client, monkeypatch):
    from backend.config import get_settings

    monkeypatch.setenv("ENVIRONMENT", "produccion")
    get_settings.cache_clear()
    try:
        respuesta = client.post(
            "/api/auth/login",
            json={"correo": "demo@underwriting.io", "contrasena": "demo1234"},
        )
    finally:
        get_settings.cache_clear()

    assert respuesta.status_code == 503
