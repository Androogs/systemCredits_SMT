"""Autenticación real de la plataforma: usuario en BD + JWT.

Flujo de `autenticar`:
1. El secreto JWT debe existir (fuera de demo es obligatorio → 503).
2. Correo case-insensitive → usuario; contraseña verificada con bcrypt.
3. Solo estados `activo` y cuentas sin `bloqueado_hasta` vigente entran.
4. Fallos acumulan `intentos_fallidos_login`; al tope la cuenta se
   bloquea `auth_bloqueo_minutos` minutos.
5. Solo los roles con acceso al panel reciben token (cliente y
   contabilidad rechazan con 403, no con un token muerto).
6. Éxito y fallo quedan en `auditoria_usuario` con la IP del cliente.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.config import Settings
from backend.db_models.auth_models import Usuario
from backend.models.auth_models import (
    CambiarClaveRequest,
    ConcesionarioSesion,
    LoginRequest,
    RestablecerClaveTokenRequest,
    UsuarioAutenticado,
)
from backend.repositories.usuario_repository import UsuarioRepository
from backend.services.jwt_service import JwtService


class AutenticacionService:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings
        self.repo = UsuarioRepository(db)
        self.jwt = JwtService(settings)

    def autenticar(
        self, payload: LoginRequest, ip: str | None = None
    ) -> tuple[UsuarioAutenticado, str, str]:
        if not self.jwt.secreto_configurado():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="La autenticación no está configurada en este entorno.",
            )

        usuario = self.repo.por_correo(payload.correo)
        if usuario is None:
            # No se audita con id_usuario (no existe) pero sí la IP:
            # patrones de fuerza bruta quedan visibles.
            self.repo.auditar(
                id_usuario=None,
                accion="login_fallido",
                descripcion=f"correo desconocido: {payload.correo.strip()[:80]}",
                ip=ip,
            )
            self._commit_fallo()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Correo o contraseña incorrectos.",
            )

        if usuario.estado != "activo" or self.repo.bloqueado(usuario):
            self.repo.auditar(
                id_usuario=usuario.id_usuario,
                accion="login_bloqueado",
                descripcion=f"estado={usuario.estado}",
                ip=ip,
            )
            self._commit_fallo()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="La cuenta no está habilitada para ingresar.",
            )

        if not self._verificar(payload.contrasena, usuario):
            self.repo.registrar_fallo(
                usuario,
                max_intentos=self.settings.auth_max_intentos,
                bloqueo_minutos=self.settings.auth_bloqueo_minutos,
            )
            self.repo.auditar(
                id_usuario=usuario.id_usuario,
                accion="login_fallido",
                ip=ip,
            )
            self._commit_fallo()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Correo o contraseña incorrectos.",
            )

        roles = self.repo.roles_de(usuario.id_usuario)
        roles_panel = [
            rol for rol in roles if rol in self.settings.roles_panel_list()
        ]
        if not roles_panel:
            self.repo.auditar(
                id_usuario=usuario.id_usuario,
                accion="login_rechazado",
                descripcion="rol sin acceso al panel",
                ip=ip,
            )
            self._commit_fallo()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tu rol no tiene acceso a la plataforma.",
            )

        self.repo.registrar_acceso(usuario)
        self.repo.auditar(
            id_usuario=usuario.id_usuario,
            accion="login_exitoso",
            ip=ip,
        )

        # El rol principal (compone la vista del panel) es el de mayor
        # privilegio: el orden de AUTH_ROLES_PANEL es la prioridad; el
        # orden del JOIN de roles_de() no es determinista.
        rol_principal = next(
            (
                r
                for r in self.settings.roles_panel_list()
                if r in roles_panel
            ),
            roles_panel[0],
        )
        concesionario = self.repo.concesionario_de_asesor(
            usuario.id_usuario
        ) or self.repo.concesionario_de_concesionario(usuario.id_usuario)
        token = self.jwt.emitir(
            id_usuario=usuario.id_usuario,
            nombre=usuario.nombre_completo or usuario.correo,
            roles=roles,
        )
        refresh = self._emitir_refresh(usuario.id_usuario, ip)
        return (
            UsuarioAutenticado(
                correo=usuario.correo,
                nombre=usuario.nombre_completo or usuario.correo,
                rol=rol_principal,
                roles=roles,
                concesionario=(
                    ConcesionarioSesion(
                        id_concesionario=concesionario.id_concesionario,
                        nombre=concesionario.nombre,
                    )
                    if concesionario
                    else None
                ),
                requiere_cambio_password=usuario.requiere_cambio_password,
            ),
            token,
            refresh,
        )

    def cambiar_clave(
        self, id_usuario: uuid.UUID, payload: CambiarClaveRequest
    ) -> UsuarioAutenticado:
        """Self-service: verifica la clave actual y guarda la nueva,
        apagando `requiere_cambio_password` (clave temporal cumplida)."""
        usuario = self.repo.por_id(id_usuario)
        if usuario is None or not self._verificar(
            payload.contrasena_actual, usuario
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La contraseña actual no es correcta.",
            )
        if payload.contrasena_actual == payload.contrasena_nueva:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La nueva contraseña debe ser diferente de la actual.",
            )
        usuario.hash_contrasena = bcrypt.hashpw(
            payload.contrasena_nueva.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        usuario.requiere_cambio_password = False
        usuario.fecha_ultimo_cambio_password = datetime.now(UTC)
        self.repo.auditar(
            id_usuario=usuario.id_usuario, accion="clave_cambiada"
        )
        # Clave nueva = sesiones viejas muertas: los refresh tokens del
        # usuario se revocan; el access JWT actual expira solo.
        self.repo.revocar_refreshes_usuario(usuario.id_usuario)
        self.db.flush()

        roles = self.repo.roles_de(usuario.id_usuario)
        roles_panel = [
            rol for rol in roles if rol in self.settings.roles_panel_list()
        ]
        rol_principal = next(
            (
                r
                for r in self.settings.roles_panel_list()
                if r in roles_panel
            ),
            roles_panel[0] if roles_panel else roles[0],
        )
        concesionario = self.repo.concesionario_de_asesor(
            usuario.id_usuario
        ) or self.repo.concesionario_de_concesionario(usuario.id_usuario)
        return UsuarioAutenticado(
            correo=usuario.correo,
            nombre=usuario.nombre_completo or usuario.correo,
            rol=rol_principal,
            roles=roles,
            concesionario=(
                ConcesionarioSesion(
                    id_concesionario=concesionario.id_concesionario,
                    nombre=concesionario.nombre,
                )
                if concesionario
                else None
            ),
            requiere_cambio_password=False,
        )

    # ------------------------------------------------------------------
    # Refresh tokens (D125): sesión revocable con rotación
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_token(token: str) -> str:
        """En reposo solo vive el sha256: la BD filtrada no revela
        sesiones activas."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _emitir_refresh(
        self, id_usuario: uuid.UUID, ip: str | None
    ) -> str:
        token = secrets.token_urlsafe(48)
        self.repo.guardar_refresh(
            id_usuario=id_usuario,
            token_hash=self._hash_token(token),
            expira_en=datetime.now(UTC)
            + timedelta(days=self.settings.refresh_token_dias),
            ip=ip,
        )
        return token

    def refrescar(
        self, refresh_token: str, ip: str | None = None
    ) -> tuple[UsuarioAutenticado, str, str]:
        """Rota el refresh: el viejo queda revocado (encadenado al nuevo)
        y se emite access JWT + refresh nuevo. Un token ya usado o
        vencido → 401: re-login."""
        almacenado = self.repo.refresh_por_hash(
            self._hash_token(refresh_token)
        )
        ahora = datetime.now(UTC)
        expira = almacenado.expira_en if almacenado else None
        if expira is not None and expira.tzinfo is None:
            expira = expira.replace(tzinfo=UTC)
        if (
            almacenado is None
            or almacenado.revocado
            or expira is None
            or expira <= ahora
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="La sesión expiró. Inicia sesión de nuevo.",
            )
        usuario = self.repo.por_id(almacenado.id_usuario)
        if usuario is None or usuario.estado != "activo":
            self.repo.revocar_refresh(almacenado)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="La sesión expiró. Inicia sesión de nuevo.",
            )

        roles = self.repo.roles_de(usuario.id_usuario)
        roles_panel = [
            rol for rol in roles if rol in self.settings.roles_panel_list()
        ]
        rol_principal = next(
            (
                r
                for r in self.settings.roles_panel_list()
                if r in roles_panel
            ),
            roles_panel[0] if roles_panel else roles[0],
        )
        concesionario = self.repo.concesionario_de_asesor(
            usuario.id_usuario
        ) or self.repo.concesionario_de_concesionario(usuario.id_usuario)
        access = self.jwt.emitir(
            id_usuario=usuario.id_usuario,
            nombre=usuario.nombre_completo or usuario.correo,
            roles=roles,
        )
        nuevo_refresh = self._emitir_refresh(usuario.id_usuario, ip)
        self.repo.revocar_refresh(
            almacenado,
            reemplazado_por=self.repo.refresh_por_hash(
                self._hash_token(nuevo_refresh)
            ).id_refresh,
        )
        self.repo.auditar(
            id_usuario=usuario.id_usuario,
            accion="sesion_renovada",
            ip=ip,
        )
        return (
            UsuarioAutenticado(
                correo=usuario.correo,
                nombre=usuario.nombre_completo or usuario.correo,
                rol=rol_principal,
                roles=roles,
                concesionario=(
                    ConcesionarioSesion(
                        id_concesionario=concesionario.id_concesionario,
                        nombre=concesionario.nombre,
                    )
                    if concesionario
                    else None
                ),
                requiere_cambio_password=usuario.requiere_cambio_password,
            ),
            access,
            nuevo_refresh,
        )

    def cerrar_sesion(
        self, refresh_token: str | None, ip: str | None = None
    ) -> None:
        """Logout efectivo: revoca el refresh token (el access JWT
        muere solo en minutos). Idempotente: token desconocido → no-op."""
        if not refresh_token:
            return
        almacenado = self.repo.refresh_por_hash(
            self._hash_token(refresh_token)
        )
        if almacenado is None or almacenado.revocado:
            return
        self.repo.revocar_refresh(almacenado)
        self.repo.auditar(
            id_usuario=almacenado.id_usuario,
            accion="logout",
            ip=ip,
        )

    # ------------------------------------------------------------------
    # Recuperación de clave por correo (D124)
    # ------------------------------------------------------------------

    def solicitar_recuperacion(
        self, correo: str, ip: str | None = None
    ) -> None:
        """Siempre responde igual (sin enumerar cuentas). Solo si el
        correo existe y la cuenta está activa se genera el token de un
        solo uso y se envía el enlace por email."""
        usuario = self.repo.por_correo(correo)
        if usuario is None or usuario.estado != "activo":
            # Auditoría sin id_usuario cuando el correo no existe:
            # sondeos de enumeración quedan en el rastro.
            self.repo.auditar(
                id_usuario=usuario.id_usuario if usuario else None,
                accion="recuperacion_ignorada",
                descripcion=(
                    "correo desconocido o cuenta inactiva: "
                    f"{correo.strip()[:80]}"
                ),
                ip=ip,
            )
            self.db.flush()
            return

        # Un solo enlace vigente por usuario.
        self.repo.invalidar_recuperaciones_pendientes(usuario.id_usuario)
        token = secrets.token_urlsafe(48)
        minutos = self.settings.recuperacion_token_minutos
        self.repo.guardar_recuperacion(
            id_usuario=usuario.id_usuario,
            token_hash=self._hash_token(token),
            expira_en=datetime.now(UTC) + timedelta(minutes=minutos),
            ip=ip,
        )
        self.repo.auditar(
            id_usuario=usuario.id_usuario,
            accion="recuperacion_solicitada",
            ip=ip,
        )
        self.db.flush()

        enlace = (
            f"{self.settings.app_url_publica.rstrip('/')}"
            f"/restablecer-clave?token={token}"
        )
        from backend.services.notificacion_service import (
            NotificacionService,
        )

        NotificacionService().notificar(
            "recuperacion_clave",
            destino=usuario.correo,
            datos={
                "nombre": (usuario.nombre_completo or usuario.correo).split(
                    " "
                )[0],
                "enlace": enlace,
                "minutos": minutos,
            },
        )

    def restablecer_clave(
        self, payload: RestablecerClaveTokenRequest, ip: str | None = None
    ) -> None:
        """Token de un solo uso: al aplicar la clave queda marcado,
        todas las sesiones del usuario se revocan y el flag de clave
        temporal se apaga."""
        almacenado = self.repo.recuperacion_por_hash(
            self._hash_token(payload.token)
        )
        ahora = datetime.now(UTC)
        expira = almacenado.expira_en if almacenado else None
        if expira is not None and expira.tzinfo is None:
            expira = expira.replace(tzinfo=UTC)
        if (
            almacenado is None
            or almacenado.usado
            or expira is None
            or expira <= ahora
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El enlace es inválido o ya venció. Solicita uno nuevo.",
            )
        usuario = self.repo.por_id(almacenado.id_usuario)
        if usuario is None or usuario.estado != "activo":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El enlace es inválido o ya venció. Solicita uno nuevo.",
            )

        usuario.hash_contrasena = bcrypt.hashpw(
            payload.contrasena_nueva.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        usuario.requiere_cambio_password = False
        usuario.fecha_ultimo_cambio_password = ahora
        almacenado.usado = True
        almacenado.fecha_uso = ahora
        # Restablecer la clave cierra todas las sesiones abiertas.
        self.repo.revocar_refreshes_usuario(usuario.id_usuario)
        self.repo.auditar(
            id_usuario=usuario.id_usuario,
            accion="clave_restaurada",
            ip=ip,
        )
        self.db.flush()

    def _commit_fallo(self) -> None:
        """La auditoría y los contadores de fallo deben sobrevivir al
        error: `get_db` hace rollback cuando el endpoint lanza
        HTTPException, así que estos datos se confirman antes."""
        self.db.commit()

    @staticmethod
    def _verificar(contrasena: str, usuario: Usuario) -> bool:
        try:
            return bcrypt.checkpw(
                contrasena.encode("utf-8"),
                usuario.hash_contrasena.encode("utf-8"),
            )
        except ValueError:
            return False
