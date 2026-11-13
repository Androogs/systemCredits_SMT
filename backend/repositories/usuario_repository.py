"""Acceso a datos de identidad: usuario, roles, asesor, aliado y auditoría."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.db_models.auth_models import (
    AliadoConcesionario,
    AliadoUsuario,
    Asesor,
    AsesorHistorial,
    AuditoriaUsuario,
    Concesionario,
    ConcesionarioUsuario,
    RefreshToken,
    Rol,
    TokenRecuperacion,
    Usuario,
    UsuarioMarca,
    UsuarioRol,
)


class UsuarioRepository:
    def __init__(self, db: Session):
        self.db = db

    def por_correo(self, correo: str) -> Usuario | None:
        """Case-insensitive: CITEXT en Postgres; lower() replica en SQLite."""
        return (
            self.db.query(Usuario)
            .filter(func.lower(Usuario.correo) == correo.strip().lower())
            .one_or_none()
        )

    def por_id(self, id_usuario: uuid.UUID) -> Usuario | None:
        return (
            self.db.query(Usuario)
            .filter(Usuario.id_usuario == id_usuario)
            .one_or_none()
        )

    def roles_de(self, id_usuario: uuid.UUID) -> list[str]:
        return [
            fila[0]
            for fila in self.db.execute(
                select(Rol.nombre)
                .join(UsuarioRol, UsuarioRol.id_rol == Rol.id_rol)
                .where(UsuarioRol.id_usuario == id_usuario)
            ).all()
        ]

    def asesor_de(self, id_usuario: uuid.UUID) -> Asesor | None:
        return (
            self.db.query(Asesor)
            .filter(Asesor.id_usuario == id_usuario)
            .one_or_none()
        )

    def concesionario_de_asesor(
        self, id_usuario: uuid.UUID
    ) -> Concesionario | None:
        return (
            self.db.query(Concesionario)
            .join(Asesor, Asesor.id_concesionario == Concesionario.id_concesionario)
            .filter(Asesor.id_usuario == id_usuario)
            .one_or_none()
        )

    def concesionario_de_concesionario(
        self, id_usuario: uuid.UUID
    ) -> Concesionario | None:
        """Sede que administra un usuario con rol `concesionario`. El
        vínculo vive en `concesionario_usuario` — no en `asesor`, porque
        el administrador no es radicador (no aparece en el catálogo de
        asesores que usa el filtro del aliado)."""
        return (
            self.db.query(Concesionario)
            .join(
                ConcesionarioUsuario,
                ConcesionarioUsuario.id_concesionario
                == Concesionario.id_concesionario,
            )
            .filter(ConcesionarioUsuario.id_usuario == id_usuario)
            .one_or_none()
        )

    def asesor_por_id(self, id_asesor: int) -> Asesor | None:
        return (
            self.db.query(Asesor)
            .filter(Asesor.id_asesor == id_asesor)
            .one_or_none()
        )

    def asesores_de_concesionario(
        self, id_concesionario: int
    ) -> list[Asesor]:
        return (
            self.db.query(Asesor)
            .filter(Asesor.id_concesionario == id_concesionario)
            .order_by(Asesor.nombre)
            .all()
        )

    def usuarios_de_concesionario(
        self, id_concesionario: int
    ) -> list[Usuario]:
        """Usuarios (asesores) cuya ficha `asesor` pertenece a la sede —
        el alcance de gestión de usuarios del rol concesionario."""
        return (
            self.db.query(Usuario)
            .join(Asesor, Asesor.id_usuario == Usuario.id_usuario)
            .filter(Asesor.id_concesionario == id_concesionario)
            .order_by(Usuario.correo)
            .all()
        )

    def concesionario_por_id(
        self, id_concesionario: int
    ) -> Concesionario | None:
        return (
            self.db.query(Concesionario)
            .filter(Concesionario.id_concesionario == id_concesionario)
            .one_or_none()
        )

    def ciudad_nombre(self, id_ciudad: int | None) -> str | None:
        """Nombre de la ciudad (la ciudad del asesor se deriva de la
        sede — se muestra readonly en la ficha)."""
        if id_ciudad is None:
            return None
        from backend.db_models.models import Ciudad

        fila = (
            self.db.query(Ciudad.nombre)
            .filter(Ciudad.id_ciudad == id_ciudad)
            .one_or_none()
        )
        return fila[0] if fila else None

    def historial_asesor(self, id_asesor: int) -> list[dict]:
        """Historial de la cuenta, más reciente primero, con el nombre
        de quien ejecutó cada cambio."""
        filas = (
            self.db.query(
                AsesorHistorial.fecha,
                AsesorHistorial.cambios,
                Usuario.nombre_completo,
            )
            .outerjoin(
                Usuario,
                Usuario.id_usuario == AsesorHistorial.id_usuario_cambio,
            )
            .filter(AsesorHistorial.id_asesor == id_asesor)
            .order_by(AsesorHistorial.fecha.desc())
            .all()
        )
        return [
            {
                "fecha": fecha,
                "cambios": cambios,
                "nombre_quien": nombre,
            }
            for fecha, cambios, nombre in filas
        ]

    def aliados_de(self, id_usuario: uuid.UUID) -> list[int]:
        return [
            fila[0]
            for fila in self.db.execute(
                select(AliadoUsuario.id_aliado).where(
                    AliadoUsuario.id_usuario == id_usuario
                )
            ).all()
        ]

    def concesionarios_de_aliado(self, id_usuario: uuid.UUID) -> list[int]:
        """Concesionarios vigentes del aliado del usuario: respeta
        `activo` y la ventana fecha_inicio/fecha_fin del vínculo."""
        hoy = datetime.now(timezone.utc).date()
        return [
            fila[0]
            for fila in self.db.execute(
                select(AliadoConcesionario.id_concesionario)
                .join(
                    AliadoUsuario,
                    AliadoUsuario.id_aliado == AliadoConcesionario.id_aliado,
                )
                .where(
                    AliadoUsuario.id_usuario == id_usuario,
                    AliadoConcesionario.activo.is_(True),
                    (AliadoConcesionario.fecha_inicio.is_(None))
                    | (func.date(AliadoConcesionario.fecha_inicio) <= hoy),
                    (AliadoConcesionario.fecha_fin.is_(None))
                    | (func.date(AliadoConcesionario.fecha_fin) >= hoy),
                )
            ).all()
        ]

    def registrar_acceso(self, usuario: Usuario) -> None:
        usuario.fecha_ultimo_acceso = datetime.now(timezone.utc)
        usuario.intentos_fallidos_login = 0
        usuario.bloqueado_hasta = None
        self.db.flush()

    def registrar_fallo(
        self, usuario: Usuario, max_intentos: int, bloqueo_minutos: int
    ) -> None:
        usuario.intentos_fallidos_login = (
            (usuario.intentos_fallidos_login or 0) + 1
        )
        if usuario.intentos_fallidos_login >= max_intentos:
            usuario.bloqueado_hasta = datetime.now(timezone.utc) + timedelta(
                minutes=bloqueo_minutos
            )
            usuario.intentos_fallidos_login = 0
        self.db.flush()

    def bloqueado(self, usuario: Usuario) -> bool:
        if usuario.bloqueado_hasta is None:
            return False
        # SQLite devuelve datetimes naive; Postgres los trae con tz.
        hasta = usuario.bloqueado_hasta
        if hasta.tzinfo is None:
            hasta = hasta.replace(tzinfo=timezone.utc)
        return hasta > datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # Gestión de usuarios (pantalla Ajustes, solo admin)
    # ------------------------------------------------------------------

    def listar_todos(self) -> list[Usuario]:
        return (
            self.db.query(Usuario)
            .order_by(Usuario.correo)
            .all()
        )

    def roles_disponibles(self) -> list[Rol]:
        return self.db.query(Rol).order_by(Rol.id_rol).all()

    def rol_por_nombre(self, nombre: str) -> Rol | None:
        return (
            self.db.query(Rol).filter(Rol.nombre == nombre).one_or_none()
        )

    def concesionarios(self) -> list[Concesionario]:
        return (
            self.db.query(Concesionario)
            .order_by(Concesionario.nombre)
            .all()
        )

    def aliados(self) -> list:
        from backend.db_models.models import AliadoFinanciero

        return (
            self.db.query(AliadoFinanciero)
            .filter(AliadoFinanciero.activo.is_(True))
            .order_by(AliadoFinanciero.nombre)
            .all()
        )

    def marcas(self) -> list[str]:
        """Marcas presentes en la BD: catálogo vigente de vehículos más
        las que ya registran las solicitudes (cargue histórico)."""
        from sqlalchemy.exc import OperationalError

        from backend.db_models.models import (
            ProductoVehiculo,
            VehiculoCatalogo,
        )

        try:
            catalogo = self.db.execute(
                select(VehiculoCatalogo.marca)
                .distinct()
                .where(VehiculoCatalogo.activo.is_(True))
            ).scalars()
        except OperationalError:
            # BD local sin la tabla del catálogo: solo marcas radicadas.
            self.db.rollback()
            catalogo = []
        usadas = self.db.execute(
            select(ProductoVehiculo.marca)
            .distinct()
            .where(ProductoVehiculo.marca.is_not(None))
        ).scalars()
        return sorted({m for m in (*catalogo, *usadas) if m})

    def asesores(self) -> list[Asesor]:
        """Todos los asesores registrados — las radicaciones históricas
        de asesores sin usuario activo siguen siendo filtrables."""
        return self.db.query(Asesor).order_by(Asesor.nombre).all()

    def guardar(self, usuario: Usuario) -> Usuario:
        self.db.add(usuario)
        self.db.flush()
        return usuario

    def asignar_roles(self, usuario: Usuario, roles: list[str]) -> None:
        """Reemplaza los roles del usuario por los dados."""
        self.db.query(UsuarioRol).filter(
            UsuarioRol.id_usuario == usuario.id_usuario
        ).delete()
        for nombre in roles:
            rol = self.rol_por_nombre(nombre)
            if rol is not None:
                self.db.add(
                    UsuarioRol(id_usuario=usuario.id_usuario, id_rol=rol.id_rol)
                )

    def marcas_de(self, id_usuario) -> list[str]:
        """Marcas de la ficha del usuario, en orden alfabético."""
        return [
            m
            for (m,) in self.db.execute(
                select(UsuarioMarca.marca)
                .where(UsuarioMarca.id_usuario == id_usuario)
                .order_by(UsuarioMarca.marca)
            )
        ]

    def marcas_por_usuarios(self, ids) -> dict:
        """id_usuario → marcas, en una sola consulta (listado admin)."""
        if not ids:
            return {}
        filas = self.db.execute(
            select(UsuarioMarca.id_usuario, UsuarioMarca.marca)
            .where(UsuarioMarca.id_usuario.in_(ids))
            .order_by(UsuarioMarca.marca)
        )
        out: dict = {}
        for id_u, marca in filas:
            out.setdefault(id_u, []).append(marca)
        return out

    def asignar_marcas(self, usuario: Usuario, marcas: list[str]) -> None:
        """Reemplaza el conjunto de marcas de la ficha (ya normalizado
        por el servicio: sin vacíos ni repetidas)."""
        self.db.query(UsuarioMarca).filter(
            UsuarioMarca.id_usuario == usuario.id_usuario
        ).delete()
        for nombre in marcas:
            self.db.add(
                UsuarioMarca(id_usuario=usuario.id_usuario, marca=nombre)
            )
        self.db.flush()

    def vincular_sede_asesor(
        self, usuario: Usuario, id_concesionario: int | None
    ) -> None:
        """Upsert/quita la sede del asesor. Sin fila de asesor se crea
        una con el nombre del usuario; `None` quita el vínculo."""
        asesor = self.asesor_de(usuario.id_usuario)
        if asesor is None and id_concesionario is not None:
            self.db.add(
                Asesor(
                    id_usuario=usuario.id_usuario,
                    nombre=usuario.nombre_completo or usuario.correo,
                    id_concesionario=id_concesionario,
                )
            )
        elif asesor is not None:
            asesor.id_concesionario = id_concesionario
        self.db.flush()

    def vincular_sede_concesionario(
        self, usuario: Usuario, id_concesionario: int | None
    ) -> None:
        """Upsert/quita la sede administrada por el rol concesionario.
        `None` quita el vínculo."""
        self.db.query(ConcesionarioUsuario).filter(
            ConcesionarioUsuario.id_usuario == usuario.id_usuario
        ).delete()
        if id_concesionario is not None:
            self.db.add(
                ConcesionarioUsuario(
                    id_usuario=usuario.id_usuario,
                    id_concesionario=id_concesionario,
                )
            )
        self.db.flush()

    def vincular_aliado(
        self, usuario: Usuario, id_aliado: int | None
    ) -> None:
        """El usuario aliado pertenece a un único aliado financiero."""
        self.db.query(AliadoUsuario).filter(
            AliadoUsuario.id_usuario == usuario.id_usuario
        ).delete()
        if id_aliado is not None:
            self.db.add(
                AliadoUsuario(
                    id_usuario=usuario.id_usuario, id_aliado=id_aliado
                )
            )
        self.db.flush()

    def otros_admins_activos(self, excluir: uuid.UUID) -> int:
        return self.db.execute(
            select(func.count(UsuarioRol.id_usuario))
            .join(Rol, UsuarioRol.id_rol == Rol.id_rol)
            .join(Usuario, UsuarioRol.id_usuario == Usuario.id_usuario)
            .where(
                Rol.nombre == "admin",
                Usuario.estado == "activo",
                UsuarioRol.id_usuario != excluir,
            )
        ).scalar_one()

    # ------------------------------------------------------------------
    # Sesiones persistidas (refresh tokens) y recuperación de clave
    # ------------------------------------------------------------------

    def guardar_refresh(
        self,
        *,
        id_usuario: uuid.UUID,
        token_hash: str,
        expira_en: datetime,
        ip: str | None,
    ) -> RefreshToken:
        token = RefreshToken(
            id_usuario=id_usuario,
            token_hash=token_hash,
            expira_en=expira_en,
            ip=ip,
        )
        self.db.add(token)
        self.db.flush()
        return token

    def refresh_por_hash(self, token_hash: str) -> RefreshToken | None:
        return (
            self.db.query(RefreshToken)
            .filter(RefreshToken.token_hash == token_hash)
            .one_or_none()
        )

    def revocar_refresh(
        self, token: RefreshToken, reemplazado_por: int | None = None
    ) -> None:
        token.revocado = True
        token.fecha_revocacion = datetime.now(timezone.utc)
        if reemplazado_por is not None:
            token.reemplazado_por = reemplazado_por
        self.db.flush()

    def revocar_refreshes_usuario(self, id_usuario: uuid.UUID) -> int:
        """Cierra todas las sesiones persistidas del usuario (cambio o
        restablecimiento de clave, bloqueo, etc.)."""
        ahora = datetime.now(timezone.utc)
        cantidad = (
            self.db.query(RefreshToken)
            .filter(
                RefreshToken.id_usuario == id_usuario,
                RefreshToken.revocado.is_(False),
            )
            .update({"revocado": True, "fecha_revocacion": ahora})
        )
        self.db.flush()
        return cantidad

    def guardar_recuperacion(
        self,
        *,
        id_usuario: uuid.UUID,
        token_hash: str,
        expira_en: datetime,
        ip: str | None,
    ) -> TokenRecuperacion:
        token = TokenRecuperacion(
            id_usuario=id_usuario,
            token_hash=token_hash,
            expira_en=expira_en,
            ip=ip,
        )
        self.db.add(token)
        self.db.flush()
        return token

    def recuperacion_por_hash(self, token_hash: str) -> TokenRecuperacion | None:
        return (
            self.db.query(TokenRecuperacion)
            .filter(TokenRecuperacion.token_hash == token_hash)
            .one_or_none()
        )

    def invalidar_recuperaciones_pendientes(self, id_usuario: uuid.UUID) -> None:
        """Solo el último enlace de recuperación queda vigente: pedir
        uno nuevo mata los anteriores sin usar."""
        (
            self.db.query(TokenRecuperacion)
            .filter(
                TokenRecuperacion.id_usuario == id_usuario,
                TokenRecuperacion.usado.is_(False),
            )
            .update({"usado": True, "fecha_uso": datetime.now(timezone.utc)})
        )
        self.db.flush()

    def auditar(
        self,
        *,
        id_usuario: uuid.UUID | None,
        accion: str,
        descripcion: str | None = None,
        ip: str | None = None,
    ) -> None:
        self.db.add(
            AuditoriaUsuario(
                id_usuario=id_usuario,
                accion=accion,
                descripcion=descripcion,
                ip=ip,
            )
        )
        self.db.flush()
