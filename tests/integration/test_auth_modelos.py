"""Las tablas de identidad existen en el esquema y son insertables.

Cubre el modelo de datos de autenticación (usuario/rol/asesor/aliado) y
el vínculo asesor→concesionario que habilita el alcance por sede.
"""

import uuid

from sqlalchemy import text

from backend.db_models.session import SessionLocal


def test_tablas_identidad_existen_y_aceptan_registros(client):
    with SessionLocal() as db:
        # Los roles ya vienen sembrados por el fixture `client`; el test
        # solo necesita que existan.
        db.execute(
            text(
                "INSERT OR IGNORE INTO rol (nombre, descripcion) VALUES "
                "('admin', 'Administrador'), ('asesor', 'Asesor'), "
                "('aliado', 'Aliado comercial')"
            )
        )
        id_usuario = uuid.uuid4()
        db.execute(
            text(
                "INSERT INTO usuario (id_usuario, correo, hash_contrasena, "
                "estado, nombre_completo) VALUES (:u, :c, :h, 'activo', :n)"
            ),
            {
                "u": str(id_usuario),
                "c": "asesor.modelos@sumoto.com.co",
                "h": "hash",
                "n": "Asesor Uno",
            },
        )
        db.execute(
            text("INSERT INTO concesionario (nombre) VALUES ('SUMOTO TEST')")
        )
        id_concesionario = db.execute(
            text("SELECT id_concesionario FROM concesionario WHERE nombre='SUMOTO TEST'")
        ).scalar_one()
        db.execute(
            text(
                "INSERT INTO asesor (id_usuario, nombre, id_concesionario) "
                "VALUES (:u, 'Asesor Uno', :c)"
            ),
            {"u": str(id_usuario), "c": id_concesionario},
        )
        db.commit()

        asesor = db.execute(
            text(
                "SELECT a.nombre, a.id_concesionario FROM asesor a "
                "JOIN usuario u ON u.id_usuario = a.id_usuario "
                "WHERE u.correo = 'asesor.modelos@sumoto.com.co'"
            )
        ).one()
    assert asesor[0] == "Asesor Uno"
    assert asesor[1] == id_concesionario


def test_solicitud_persiste_concesionario_del_asesor(client):
    """La radicación queda ligada al concesionario: el alcance del asesor
    y del aliado se filtra por esta columna."""
    from backend.db_models.models import Cliente, SolicitudCredito

    with SessionLocal() as db:
        db.execute(
            text("INSERT INTO concesionario (nombre) VALUES ('TULUA TEST')")
        )
        id_concesionario = db.execute(
            text("SELECT id_concesionario FROM concesionario WHERE nombre='TULUA TEST'")
        ).scalar_one()
        from datetime import date

        cliente = Cliente(
            tipo_documento="CC",
            num_cedula="999000111",
            nombre_completo="Cliente Prueba",
            fecha_nacimiento=date(1990, 1, 1),
        )
        db.add(cliente)
        db.flush()
        solicitud = SolicitudCredito(
            id_cliente=cliente.id_cliente,
            id_concesionario=id_concesionario,
            estado="creada",
        )
        db.add(solicitud)
        db.commit()
        assert solicitud.id_concesionario == id_concesionario
