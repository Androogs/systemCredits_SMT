"""Headers de seguridad HTTP: defensa en profundidad para respuestas
que sirven contenido subido por usuarios (evidencias, paquetes)."""


def test_respuestas_llevan_headers_de_seguridad(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "no-referrer"


def test_errores_tambien_llevan_headers(client):
    r = client.get("/api/firmas/no-es-uuid")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
