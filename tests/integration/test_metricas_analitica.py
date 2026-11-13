"""Analítica del portafolio: efectividad por sede y por marca.

La marca se toma del vehículo a financiar (`producto_vehiculo.marca`)
normalizada con la misma etiqueta que los segmentos de campaña; las
solicitudes sin vehículo quedan en 'Sin dato', siempre al final.
"""

import uuid
from datetime import date, datetime

from backend.db_models import session as db_session
from backend.db_models.models import (
    Cliente,
    ProductoVehiculo,
    SolicitudCredito,
)


def _sembrar(db, num_solicitud: int, marca: str | None = None,
             fecha: datetime = datetime(2026, 11, 3)) -> SolicitudCredito:
    cliente = Cliente(
        tipo_documento="1",
        num_cedula=f"880{num_solicitud}",
        nombre_completo="CLIENTE PRUEBA",
        primer_apellido="PRUEBA",
        fecha_nacimiento=date(1995, 3, 8),
        ocupacion="empleado",
    )
    db.add(cliente)
    db.flush()
    solicitud = SolicitudCredito(
        id_solicitud=uuid.uuid4(),
        num_solicitud=num_solicitud,
        id_cliente=cliente.id_cliente,
        fecha_hora=fecha,
        estado="creada",
        moneda="COP",
        origen="flujo",
    )
    db.add(solicitud)
    db.flush()
    if marca is not None:
        db.add(
            ProductoVehiculo(
                id_solicitud=solicitud.id_solicitud,
                producto_a_financiar="Motocicleta",
                marca=marca,
            )
        )
    db.commit()
    return solicitud


def test_por_marca_agrupa_por_vehiculo(client):
    db = db_session.SessionLocal()
    _sembrar(db, 980001, marca="YAMAHA")
    _sembrar(db, 980002, marca="YAMAHA")
    _sembrar(db, 980003, marca="Suzuki")
    _sembrar(db, 980004)  # sin vehículo → 'Sin dato'
    db.close()

    r = client.get("/api/solicitudes/metricas/analitica")
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["total_radicadas"] == 4

    filas = {f["nombre"]: f for f in cuerpo["por_marca"]}
    # Misma normalización que el segmento 'Marca' de campañas.
    assert filas["Yamaha"]["radicadas"] == 2
    assert filas["Suzuki"]["radicadas"] == 1
    assert filas["Sin dato"]["radicadas"] == 1
    # 'Sin dato' al final aunque empate en volumen con otras marcas.
    assert cuerpo["por_marca"][-1]["nombre"] == "Sin dato"


def test_rango_acota_por_fecha_radicacion(client):
    db = db_session.SessionLocal()
    _sembrar(db, 980011, marca="YAMAHA", fecha=datetime(2026, 10, 15))
    _sembrar(db, 980012, marca="YAMAHA", fecha=datetime(2026, 11, 5))
    db.close()

    r = client.get(
        "/api/solicitudes/metricas/analitica?desde=2026-11-01&hasta=2026-11-30"
    )
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["total_radicadas"] == 1
    assert cuerpo["historico_completo"] is False
    assert [f["nombre"] for f in cuerpo["por_marca"]] == ["Yamaha"]


def test_rol_sin_permiso(client_asesor):
    r = client_asesor.get("/api/solicitudes/metricas/analitica")
    assert r.status_code == 403
