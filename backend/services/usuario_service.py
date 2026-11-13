"""Gestión de usuarios desde Ajustes.

Cubre alta, edición de nombre/estado/roles, vínculos asesor→sede,
usuario→aliado y usuario→sede (concesionario), y restablecimiento de
clave. Todo cambio queda en `auditoria_usuario` con el id del usuario
que lo ejecutó.

Alcance: el admin ve y gestiona todo; el concesionario solo los
asesores de su propia sede (crear/editar/activar/restablecer clave) —
nunca otros roles, otras sedes ni usuarios fuera de ella.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import bcrypt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.auth.dependencies import UsuarioActual
from backend.db_models.auth_models import (
    Asesor,
    AsesorHistorial,
    Usuario,
)
from backend.models.auth_models import (
    ActualizarUsuarioRequest,
    AliadoOpcion,
    AsesorHistorialResponse,
    AsesorOpcion,
    ConcesionarioSesion,
    CrearUsuarioRequest,
    OpcionesUsuarioResponse,
    RolOpcion,
    UsuarioGestionResponse,
)
from backend.repositories.usuario_repository import UsuarioRepository
from backend.services.motor_exceptions import (
    ConflictoEstadoError,
    SolicitudNoEncontradaError,
    ValidacionError,
)

_ESTADOS_EDITABLES = {"activo", "bloqueado", "inactivo"}

# Centinela: distingue "campo ausente del payload" de "campo presente
# con None" (limpiar el vínculo). `model_fields_set` decide en cada
# llamada si se pasa el valor real o el centinela.
_SIN_CAMBIO = object()


def _normalizar_marcas(
    marcas: list[str] | None, marca_legado: str | None
) -> list[str]:
    """Conjunto de marcas de la ficha: limpia espacios, deduplica
    (case-insensitive) y conserva el orden recibido — la primera queda
    como principal en `usuario.marca`. `marcas` (nuevo) gana sobre
    `marca` (legado, valor único)."""
    fuente = (
        marcas
        if marcas is not None
        else ([marca_legado] if marca_legado else [])
    )
    vistas: set[str] = set()
    out: list[str] = []
    for m in fuente:
        nombre = " ".join(str(m).split()).strip()[:120]
        clave = nombre.upper()
        if nombre and clave not in vistas:
            vistas.add(clave)
            out.append(nombre)
    return out


class UsuarioService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = UsuarioRepository(db)

    def listar(
        self, actor: UsuarioActual
    ) -> list[UsuarioGestionResponse]:
        usuarios = (
            self.repo.listar_todos()
            if actor.es_admin()
            else self.repo.usuarios_de_concesionario(
                self._sede_del_actor(actor)
            )
        )
        marcas_map = self.repo.marcas_por_usuarios(
            [u.id_usuario for u in usuarios]
        )
        return [
            self._gestion(u, marcas_map.get(u.id_usuario, []))
            for u in usuarios
        ]

    def opciones(
        self, actor: UsuarioActual
    ) -> OpcionesUsuarioResponse:
        if actor.es_admin():
            return OpcionesUsuarioResponse(
                roles=[
                    RolOpcion(id_rol=r.id_rol, nombre=r.nombre)
                    for r in self.repo.roles_disponibles()
                ],
                concesionarios=[
                    ConcesionarioSesion(
                        id_concesionario=c.id_concesionario,
                        nombre=c.nombre,
                        ciudad=self.repo.ciudad_nombre(c.id_ciudad),
                    )
                    for c in self.repo.concesionarios()
                ],
                aliados=[
                    AliadoOpcion(id_aliado=a.id_aliado, nombre=a.nombre)
                    for a in self.repo.aliados()
                ],
                asesores=[
                    AsesorOpcion(
                        id_asesor=a.id_asesor,
                        nombre=a.nombre,
                        id_concesionario=a.id_concesionario,
                    )
                    for a in self.repo.asesores()
                ],
                marcas=self.repo.marcas(),
            )
        sede = self._sede_del_actor(actor)
        rol_asesor = self.repo.rol_por_nombre("asesor")
        concesionario = self.repo.concesionario_de_concesionario(
            actor.id_usuario
        )
        return OpcionesUsuarioResponse(
            roles=(
                [RolOpcion(id_rol=rol_asesor.id_rol, nombre="asesor")]
                if rol_asesor
                else []
            ),
            concesionarios=(
                [
                    ConcesionarioSesion(
                        id_concesionario=concesionario.id_concesionario,
                        nombre=concesionario.nombre,
                        ciudad=self.repo.ciudad_nombre(
                            concesionario.id_ciudad
                        ),
                    )
                ]
                if concesionario
                else []
            ),
            aliados=[],
            asesores=[
                AsesorOpcion(
                    id_asesor=a.id_asesor,
                    nombre=a.nombre,
                    id_concesionario=a.id_concesionario,
                )
                for a in self.repo.asesores_de_concesionario(sede)
            ],
            marcas=self.repo.marcas(),
        )

    def crear(
        self, payload: CrearUsuarioRequest, admin: UsuarioActual
    ) -> UsuarioGestionResponse:
        if not admin.es_admin():
            # El concesionario solo da de alta asesores de su sede.
            sede = self._sede_del_actor(admin)
            if set(payload.roles) != {"asesor"}:
                raise ValidacionError(
                    "Solo puedes crear usuarios con rol asesor de tu sede."
                )
            payload = payload.model_copy(
                update={"id_concesionario": sede, "id_aliado": None}
            )
        correo = payload.correo.strip().lower()
        if self.repo.por_correo(correo) is not None:
            raise ConflictoEstadoError(f"Ya existe un usuario con {correo}")
        self._validar_roles(payload.roles)
        if "asesor" in payload.roles:
            self._validar_ficha_asesor(payload)
        marcas = _normalizar_marcas(payload.marcas, payload.marca)

        usuario = self.repo.guardar(
            Usuario(
                id_usuario=uuid.uuid4(),
                correo=correo,
                hash_contrasena=self._hash(payload.contrasena),
                estado="activo",
                nombre_completo=payload.nombre.strip(),
                cedula=(payload.cedula or "").strip() or None,
                marca=marcas[0] if marcas else None,
                sede=(payload.sede or "").strip() or None,
                observaciones=(payload.observaciones or "").strip() or None,
                requiere_cambio_password=True,
            )
        )
        self.repo.asignar_roles(usuario, payload.roles)
        self.repo.asignar_marcas(usuario, marcas)
        self._vincular_sede(
            usuario,
            payload.id_concesionario,
            cedula=payload.cedula,
            telefono=payload.telefono,
            actor=admin,
        )
        self.repo.vincular_aliado(usuario, payload.id_aliado)
        self.repo.auditar(
            id_usuario=admin.id_usuario,
            accion="usuario_creado",
            descripcion=f"{correo} roles={sorted(payload.roles)}",
        )
        try:
            self.db.flush()
        except IntegrityError as exc:
            raise ConflictoEstadoError(
                f"Ya existe un usuario con {correo}"
            ) from exc
        return self._gestion(usuario)

    def actualizar(
        self,
        id_usuario: uuid.UUID,
        payload: ActualizarUsuarioRequest,
        admin: UsuarioActual,
    ) -> UsuarioGestionResponse:
        usuario = self.repo.por_id(id_usuario)
        if usuario is None:
            raise SolicitudNoEncontradaError("Usuario no encontrado")

        cambios = payload.model_fields_set
        historial: dict = {}
        if not admin.es_admin():
            # El concesionario solo toca asesores de su propia sede y
            # no puede cambiarles el rol ni moverlos de sede ni aliado.
            self._verificar_objetivo_de_sede(id_usuario, admin)
            if "roles" in cambios and set(payload.roles or []) != {
                "asesor"
            }:
                raise ValidacionError(
                    "Solo puedes gestionar usuarios con rol asesor."
                )
            if (
                "id_concesionario" in cambios
                and payload.id_concesionario != admin.id_concesionario
            ):
                raise ValidacionError(
                    "El asesor solo puede pertenecer a tu sede."
                )
            if "id_aliado" in cambios and payload.id_aliado is not None:
                raise ValidacionError(
                    "No puedes vincular aliados a los asesores."
                )
        # Protección de la puerta: el admin no puede apagar su propia
        # cuenta ni dejar la plataforma sin un administrador activo.
        if id_usuario == admin.id_usuario:
            if "estado" in cambios and payload.estado != "activo":
                raise ValidacionError(
                    "No puedes desactivar tu propia cuenta."
                )
            if "roles" in cambios and (
                not payload.roles or "admin" not in payload.roles
            ):
                raise ValidacionError(
                    "No puedes quitarte el rol de administrador."
                )
        if "roles" in cambios:
            self._validar_roles(payload.roles or [])
            era_admin = "admin" in self.repo.roles_de(id_usuario)
            if (
                era_admin
                and "admin" not in (payload.roles or [])
                and self.repo.otros_admins_activos(id_usuario) == 0
            ):
                raise ValidacionError(
                    "Debe quedar al menos un administrador activo."
                )
            self.repo.asignar_roles(usuario, payload.roles or [])
            roles_nuevos = set(payload.roles or [])
            if "concesionario" not in roles_nuevos:
                self.repo.vincular_sede_concesionario(usuario, None)
        if "estado" in cambios and payload.estado is not None:
            if payload.estado not in _ESTADOS_EDITABLES:
                raise ValidacionError(f"Estado inválido: {payload.estado}")
            if (
                payload.estado != "activo"
                and "admin" in self.repo.roles_de(id_usuario)
                and self.repo.otros_admins_activos(id_usuario) == 0
            ):
                raise ValidacionError(
                    "Debe quedar al menos un administrador activo."
                )
            if payload.estado != usuario.estado:
                historial["estado"] = {
                    "antes": usuario.estado,
                    "despues": payload.estado,
                }
            usuario.estado = payload.estado
            if payload.estado == "activo":
                usuario.bloqueado_hasta = None
                usuario.intentos_fallidos_login = 0
        if payload.nombre is not None:
            usuario.nombre_completo = payload.nombre.strip()
        nuevas_marcas = _SIN_CAMBIO
        if "marcas" in cambios:
            nuevas_marcas = _normalizar_marcas(payload.marcas, None)
        elif "marca" in cambios:
            nuevas_marcas = _normalizar_marcas(None, payload.marca)
        if nuevas_marcas is not _SIN_CAMBIO:
            usuario.marca = nuevas_marcas[0] if nuevas_marcas else None
            self.repo.asignar_marcas(usuario, nuevas_marcas)
        if "sede" in cambios:
            usuario.sede = (payload.sede or "").strip() or None
        if "observaciones" in cambios:
            usuario.observaciones = (
                (payload.observaciones or "").strip() or None
            )
        if "cedula" in cambios and payload.cedula is not None:
            usuario.cedula = payload.cedula.strip() or None
        if ("cedula" in cambios or "telefono" in cambios) and (
            payload.cedula == "" or payload.telefono == ""
        ):
            raise ValidacionError(
                "La cédula y el celular del asesor no pueden quedar vacíos."
            )
        # La ficha se toca si viene la sede, la cédula, el celular o el
        # nombre (el nombre de la persona también vive en la ficha).
        if cambios & {
            "id_concesionario",
            "cedula",
            "telefono",
            "nombre",
            "roles",
        }:
            historial.update(
                self._vincular_sede(
                    usuario,
                    (
                        payload.id_concesionario
                        if "id_concesionario" in cambios
                        else _SIN_CAMBIO
                    ),
                    cedula=(
                        payload.cedula if "cedula" in cambios else _SIN_CAMBIO
                    ),
                    telefono=(
                        payload.telefono
                        if "telefono" in cambios
                        else _SIN_CAMBIO
                    ),
                    actor=admin,
                )
            )
        if "id_aliado" in cambios:
            self.repo.vincular_aliado(usuario, payload.id_aliado)
        # Quien gana el rol asesor debe quedar con ficha completa —
        # la cédula liga las solicitudes a la persona real.
        if "asesor" in self.repo.roles_de(id_usuario):
            ficha = self.repo.asesor_de(id_usuario)
            if ficha is not None and (
                not ficha.num_cedula or not ficha.telefono
            ):
                raise ValidacionError(
                    "El rol asesor necesita cédula y celular: envíalos "
                    "en esta edición."
                )
        if historial:
            self._registrar_historial(usuario, historial, admin)
        self.db.flush()
        self.repo.auditar(
            id_usuario=admin.id_usuario,
            accion="usuario_actualizado",
            descripcion=f"{usuario.correo} campos={sorted(cambios)}",
        )
        return self._gestion(usuario)

    def restablecer_clave(
        self,
        id_usuario: uuid.UUID,
        nueva_contrasena: str,
        admin: UsuarioActual,
    ) -> None:
        usuario = self.repo.por_id(id_usuario)
        if usuario is None:
            raise SolicitudNoEncontradaError("Usuario no encontrado")
        if not admin.es_admin():
            self._verificar_objetivo_de_sede(id_usuario, admin)
        usuario.hash_contrasena = self._hash(nueva_contrasena)
        usuario.requiere_cambio_password = True
        usuario.bloqueado_hasta = None
        usuario.intentos_fallidos_login = 0
        self.db.flush()
        self.repo.auditar(
            id_usuario=admin.id_usuario,
            accion="clave_restablecida",
            descripcion=f"para {usuario.correo}",
        )

    # ------------------------------------------------------------------

    def _sede_del_actor(self, actor: UsuarioActual) -> int:
        """Sede obligatoria del concesionario — sin vínculo en
        `concesionario_usuario` el rol no puede gestionar nada."""
        if actor.id_concesionario is None:
            raise ValidacionError(
                "Tu usuario no tiene una sede asignada. Pide al "
                "administrador que te vincule a un concesionario."
            )
        return actor.id_concesionario

    def _verificar_objetivo_de_sede(
        self, id_usuario: uuid.UUID, actor: UsuarioActual
    ) -> None:
        """404 (no 403) para no filtrar la existencia del usuario."""
        asesor = self.repo.asesor_de(id_usuario)
        if (
            asesor is None
            or asesor.id_concesionario != self._sede_del_actor(actor)
        ):
            raise SolicitudNoEncontradaError("Usuario no encontrado")

    def _validar_ficha_asesor(self, payload: CrearUsuarioRequest) -> None:
        """Alta de un asesor: la ficha completa es obligatoria (cédula y
        celular de la persona, más la sede — la ciudad se deriva de ella)."""
        faltantes = [
            campo
            for campo, valor in (
                ("cédula", payload.cedula),
                ("celular", payload.telefono),
            )
            if valor is None or not valor.strip()
        ]
        if payload.id_concesionario is None:
            faltantes.append("concesionario")
        if faltantes:
            raise ValidacionError(
                "El asesor necesita " + ", ".join(faltantes) + "."
            )

    def _vincular_sede(
        self,
        usuario: Usuario,
        id_concesionario=_SIN_CAMBIO,
        *,
        cedula=_SIN_CAMBIO,
        telefono=_SIN_CAMBIO,
        actor: UsuarioActual,
    ) -> dict:
        """Reparte el vínculo de sede según el rol y mantiene la ficha
        del asesor (nombre espejo del usuario, cédula, celular, ciudad
        de la sede). Devuelve los cambios que hubo para el historial."""
        roles = set(self.repo.roles_de(usuario.id_usuario))
        historial: dict = {}
        if "asesor" in roles:
            historial = self._guardar_ficha_asesor(
                usuario,
                id_concesionario,
                cedula=cedula,
                telefono=telefono,
            )
        if "concesionario" in roles and id_concesionario is not _SIN_CAMBIO:
            self.repo.vincular_sede_concesionario(
                usuario, id_concesionario
            )
        return historial

    def _guardar_ficha_asesor(
        self,
        usuario: Usuario,
        id_concesionario,
        *,
        cedula,
        telefono,
    ) -> dict:
        """Upsert de la ficha del asesor con diff para historial.

        La ciudad se hereda del concesionario elegido (es dato de la
        sede, no de la persona). En alta crea la ficha; en edición solo
        toca los campos que vinieron en el payload (los ausentes no se
        tocan — la cédula vieja no se pierde al cambiar el nombre)."""
        asesor = self.repo.asesor_de(usuario.id_usuario)
        cambios: dict = {}
        sede = (
            self.repo.concesionario_por_id(id_concesionario)
            if isinstance(id_concesionario, int)
            else None
        )
        nombre_ficha = usuario.nombre_completo or usuario.correo
        if asesor is None:
            asesor = Asesor(
                id_usuario=usuario.id_usuario,
                nombre=nombre_ficha,
                telefono=(
                    telefono.strip() if isinstance(telefono, str) else None
                ),
                num_cedula=(
                    cedula.strip() if isinstance(cedula, str) else None
                ),
                id_ciudad=sede.id_ciudad if sede else None,
                id_concesionario=(
                    id_concesionario
                    if isinstance(id_concesionario, int)
                    else None
                ),
            )
            self.db.add(asesor)
            self.db.flush()
            return {
                "cuenta": {"antes": None, "despues": "ficha creada"}
            }
        # Edición: diff por campo, solo los que vinieron en el payload.
        if usuario.nombre_completo and asesor.nombre != nombre_ficha:
            cambios["nombre"] = {
                "antes": asesor.nombre,
                "despues": nombre_ficha,
            }
            asesor.nombre = nombre_ficha
        if isinstance(cedula, str) and cedula.strip() != (
            asesor.num_cedula or ""
        ):
            cambios["cedula"] = {
                "antes": asesor.num_cedula,
                "despues": cedula.strip(),
            }
            asesor.num_cedula = cedula.strip()
        if isinstance(telefono, str) and telefono.strip() != (
            asesor.telefono or ""
        ):
            cambios["celular"] = {
                "antes": asesor.telefono,
                "despues": telefono.strip(),
            }
            asesor.telefono = telefono.strip()
        if id_concesionario is not _SIN_CAMBIO and (
            id_concesionario != asesor.id_concesionario
        ):
            cambios["sede"] = {
                "antes": asesor.id_concesionario,
                "despues": id_concesionario,
            }
            asesor.id_concesionario = id_concesionario
            asesor.id_ciudad = sede.id_ciudad if sede else None
        # Cambio de titular: la cédula pasa de una persona a otra
        # (valor anterior no nulo), o llega cédula junto con nombre
        # nuevo (reemplazo con ficha incompleta). Completar la cédula
        # del MISMO titular (nombre intacto) no cuenta: sus solicitudes
        # legadas sin foto le siguen perteneciendo. El corte hace que
        # las legadas del predecesor dejen de verse para el sucesor.
        if "cedula" in cambios and (
            cambios["cedula"]["antes"] or "nombre" in cambios
        ):
            asesor.persona_desde = datetime.now(UTC)
        self.db.flush()
        return cambios

    def _registrar_historial(
        self, usuario: Usuario, cambios: dict, actor: UsuarioActual
    ) -> None:
        """Un renglón en `asesor_historial` por edición que tocó la
        cuenta (solo usuarios con ficha de asesor)."""
        asesor = self.repo.asesor_de(usuario.id_usuario)
        if asesor is None or not cambios:
            return
        self.db.add(
            AsesorHistorial(
                id_asesor=asesor.id_asesor,
                id_usuario_cambio=actor.id_usuario,
                cambios=cambios,
            )
        )
        self.db.flush()

    def historial(
        self, id_usuario: uuid.UUID, actor: UsuarioActual
    ) -> list[AsesorHistorialResponse]:
        usuario = self.repo.por_id(id_usuario)
        if usuario is None:
            raise SolicitudNoEncontradaError("Usuario no encontrado")
        if not actor.es_admin():
            self._verificar_objetivo_de_sede(id_usuario, actor)
        asesor = self.repo.asesor_de(id_usuario)
        if asesor is None:
            return []
        return [
            AsesorHistorialResponse(**fila)
            for fila in self.repo.historial_asesor(asesor.id_asesor)
        ]

    def _gestion(
        self, usuario: Usuario, marcas: list[str] | None = None
    ) -> UsuarioGestionResponse:
        concesionario = self.repo.concesionario_de_asesor(
            usuario.id_usuario
        ) or self.repo.concesionario_de_concesionario(usuario.id_usuario)
        ids_aliado = self.repo.aliados_de(usuario.id_usuario)
        aliados = (
            sorted(
                (
                    AliadoOpcion(id_aliado=a.id_aliado, nombre=a.nombre)
                    for a in self.repo.aliados()
                    if a.id_aliado in ids_aliado
                ),
                key=lambda a: a.nombre,
            )
            if ids_aliado
            else []
        )
        asesor = self.repo.asesor_de(usuario.id_usuario)
        return UsuarioGestionResponse(
            id_usuario=usuario.id_usuario,
            correo=usuario.correo,
            nombre=usuario.nombre_completo,
            estado=usuario.estado,
            roles=self.repo.roles_de(usuario.id_usuario),
            concesionario=(
                ConcesionarioSesion(
                    id_concesionario=concesionario.id_concesionario,
                    nombre=concesionario.nombre,
                    ciudad=self.repo.ciudad_nombre(concesionario.id_ciudad),
                )
                if concesionario
                else None
            ),
            aliados=aliados,
            cedula=usuario.cedula or (asesor.num_cedula if asesor else None),
            telefono=asesor.telefono if asesor else None,
            marca=usuario.marca,
            marcas=(
                marcas
                if marcas is not None
                else self.repo.marcas_de(usuario.id_usuario)
            ),
            sede=usuario.sede,
            observaciones=usuario.observaciones,
            fecha_creacion=usuario.fecha_creacion,
            requiere_cambio_password=usuario.requiere_cambio_password,
            fecha_ultimo_acceso=usuario.fecha_ultimo_acceso,
            bloqueado_hasta=usuario.bloqueado_hasta,
        )

    def _validar_roles(self, roles: list[str]) -> None:
        disponibles = {r.nombre for r in self.repo.roles_disponibles()}
        desconocidos = set(roles) - disponibles
        if desconocidos:
            raise ValidacionError(
                f"Roles desconocidos: {sorted(desconocidos)}"
            )

    @staticmethod
    def _hash(contrasena: str) -> str:
        return bcrypt.hashpw(
            contrasena.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
