/** Gestión real de usuarios (solo admin): lista, crea, edita,
 * activa/desactiva y restablece claves contra /api/usuarios.
 * Los vínculos visibles dependen del rol elegido:
 * asesor → su concesionario; aliado → su aliado financiero. */

import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import {
  History,
  KeyRound,
  Pencil,
  Plus,
  UserCheck,
  UserX,
  X,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  actualizarUsuario,
  crearUsuario,
  ErrorUsuariosApi,
  listarUsuarios,
  obtenerHistorialUsuario,
  obtenerOpcionesUsuario,
  restablecerClave,
} from '../api/usuariosApi'
import type { UsuarioGestion } from '../api/usuariosApi'
import { emitirToast } from '../../../shared/lib/toastBus'
import CampoEntrada from '../../../shared/ui/CampoEntrada'

const ROTULO_ROL: Record<string, string> = {
  admin: 'Administrador',
  asesor: 'Asesor',
  aliado: 'Aliado',
  cliente: 'Cliente',
  contabilidad: 'Contabilidad',
  concesionario: 'Administrador de sede',
}

const ESTADOS: { valor: string; rotulo: string }[] = [
  { valor: 'activo', rotulo: 'Activo' },
  { valor: 'inactivo', rotulo: 'Inactivo' },
  { valor: 'bloqueado', rotulo: 'Bloqueado' },
]

interface Formulario {
  nombre: string
  correo: string
  contrasena: string
  roles: string[]
  idConcesionario: string
  idAliado: string
  /** Ficha de la persona detrás del correo (solo rol asesor). */
  cedula: string
  telefono: string
  estado: string
}

const FORM_VACIO: Formulario = {
  nombre: '',
  correo: '',
  contrasena: '',
  roles: ['asesor'],
  idConcesionario: '',
  idAliado: '',
  cedula: '',
  telefono: '',
  estado: 'activo',
}

/** Rótulos de los campos que registra el historial de la ficha. */
const ROTULO_CAMBIO: Record<string, string> = {
  nombre: 'Nombre',
  cedula: 'Cédula',
  celular: 'Celular',
  sede: 'Concesionario',
  estado: 'Estado',
  cuenta: 'Cuenta',
}

function mensajeError(causa: unknown, porDefecto: string): string {
  return causa instanceof ErrorUsuariosApi || causa instanceof Error
    ? causa.message
    : porDefecto
}

export default function GestionUsuarios() {
  const qc = useQueryClient()
  const modalRef = useRef<HTMLDivElement>(null)
  const [busqueda, setBusqueda] = useState('')
  const [modalAbierto, setModalAbierto] = useState(false)
  const [editando, setEditando] = useState<UsuarioGestion | null>(null)
  const [form, setForm] = useState<Formulario>(FORM_VACIO)
  const [errorForm, setErrorForm] = useState('')
  // Restablecer clave: acordeón dentro de la fila expandida.
  const [resetDe, setResetDe] = useState<UsuarioGestion | null>(null)
  const [nuevaClave, setNuevaClave] = useState('')
  // Historial de la ficha del asesor (la persona detrás del correo).
  const [historialDe, setHistorialDe] = useState<UsuarioGestion | null>(null)

  const consultaUsuarios = useQuery({
    queryKey: ['usuarios'],
    queryFn: listarUsuarios,
  })
  const { data: opciones } = useQuery({
    queryKey: ['usuarios-opciones'],
    queryFn: obtenerOpcionesUsuario,
  })
  const consultaHistorial = useQuery({
    queryKey: ['asesor-historial', historialDe?.id_usuario],
    queryFn: () => obtenerHistorialUsuario(historialDe!.id_usuario),
    enabled: historialDe != null,
  })
  const usuarios = consultaUsuarios.data ?? []

  const refrescar = () => {
    qc.invalidateQueries({ queryKey: ['usuarios'] })
  }

  const mutGuardar = useMutation({
    mutationFn: async () => {
      const roles = form.roles
      // La sede aplica a asesor (asesor.id_concesionario) y a
      // concesionario (concesionario_usuario): el backend la reparte.
      const pideSede =
        roles.includes('asesor') || roles.includes('concesionario')
      const idConcesionario = pideSede
        ? Number(form.idConcesionario) || null
        : null
      const idAliado = roles.includes('aliado')
        ? Number(form.idAliado) || null
        : null
      // La ficha (persona detrás del correo) solo aplica al rol asesor.
      const esAsesor = roles.includes('asesor')
      const ficha = esAsesor
        ? {
            cedula: form.cedula.trim() || null,
            telefono: form.telefono.trim() || null,
          }
        : {}
      if (editando) {
        return actualizarUsuario(editando.id_usuario, {
          nombre: form.nombre,
          estado: form.estado,
          roles,
          id_concesionario: idConcesionario,
          id_aliado: idAliado,
          ...ficha,
        })
      }
      return crearUsuario({
        nombre: form.nombre,
        correo: form.correo,
        contrasena: form.contrasena,
        roles,
        id_concesionario: idConcesionario,
        id_aliado: idAliado,
        ...ficha,
      })
    },
    onSuccess: () => {
      setModalAbierto(false)
      emitirToast({
        tipo: 'exito',
        mensaje: editando ? 'Usuario actualizado.' : 'Usuario creado.',
      })
      refrescar()
    },
    onError: (causa) =>
      setErrorForm(mensajeError(causa, 'No se pudo guardar el usuario.')),
  })

  const mutEstado = useMutation({
    mutationFn: (usuario: UsuarioGestion) =>
      actualizarUsuario(usuario.id_usuario, {
        estado: usuario.estado === 'activo' ? 'inactivo' : 'activo',
      }),
    onSuccess: refrescar,
    onError: (causa) =>
      emitirToast({
        tipo: 'error',
        mensaje: mensajeError(causa, 'No se pudo cambiar el estado.'),
      }),
  })

  const mutReset = useMutation({
    mutationFn: () => restablecerClave(resetDe!.id_usuario, nuevaClave),
    onSuccess: () => {
      emitirToast({
        tipo: 'exito',
        mensaje: `Clave restablecida para ${resetDe?.correo}. El usuario deberá cambiarla al ingresar.`,
      })
      setResetDe(null)
      setNuevaClave('')
      refrescar()
    },
    onError: (causa) =>
      emitirToast({
        tipo: 'error',
        mensaje: mensajeError(causa, 'No se pudo restablecer la clave.'),
      }),
  })

  useEffect(() => {
    if (!modalAbierto) return
    const focoPrevio =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null
    modalRef.current
      ?.querySelector<HTMLElement>('input:not([disabled])')
      ?.focus()
    return () => focoPrevio?.focus()
  }, [modalAbierto])

  const abrirCrear = () => {
    setEditando(null)
    setForm(FORM_VACIO)
    setErrorForm('')
    setModalAbierto(true)
  }

  const abrirEditar = (u: UsuarioGestion) => {
    setEditando(u)
    setForm({
      nombre: u.nombre ?? '',
      correo: u.correo,
      contrasena: '',
      roles: u.roles.length > 0 ? u.roles : ['asesor'],
      idConcesionario: u.concesionario
        ? String(u.concesionario.id_concesionario)
        : '',
      idAliado: u.aliados[0] ? String(u.aliados[0].id_aliado) : '',
      cedula: u.cedula ?? '',
      telefono: u.telefono ?? '',
      estado: u.estado,
    })
    setErrorForm('')
    setModalAbierto(true)
  }

  const alternarRol = (rol: string) => {
    setForm((f) => ({
      ...f,
      roles: f.roles.includes(rol)
        ? f.roles.filter((r) => r !== rol)
        : [...f.roles, rol],
    }))
  }

  const guardar = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setErrorForm('')
    if (form.roles.length === 0) {
      setErrorForm('Asigna al menos un rol.')
      return
    }
    if (
      (form.roles.includes('asesor') || form.roles.includes('concesionario')) &&
      !form.idConcesionario
    ) {
      setErrorForm(
        'El usuario necesita un concesionario: sin sede no puede operar.',
      )
      return
    }
    if (!editando && form.contrasena.length < 8) {
      setErrorForm('La clave temporal debe tener al menos 8 caracteres.')
      return
    }
    if (
      form.roles.includes('asesor') &&
      (!form.cedula.trim() || !form.telefono.trim())
    ) {
      setErrorForm(
        'El asesor necesita cédula y celular de la persona que usará el correo.',
      )
      return
    }
    mutGuardar.mutate()
  }

  const filtrados = usuarios.filter((u) => {
    const q = busqueda.trim().toLowerCase()
    if (!q) return true
    return (
      (u.nombre ?? '').toLowerCase().includes(q) ||
      u.correo.toLowerCase().includes(q)
    )
  })

  const rotuloRol = (r: string) => ROTULO_ROL[r] ?? r
  const estadoRotulo = (e: string) =>
    ESTADOS.find((x) => x.valor === e)?.rotulo ?? e

  return (
    <div>
      <div className="flex flex-col sm:flex-row gap-2 mb-4">
        <button
          onClick={abrirCrear}
          type="button"
          className="btn-primary flex h-11 items-center justify-center gap-2 sm:h-9"
        >
          <Plus className="h-4 w-4" /> Crear usuario
        </button>
        <input
          aria-label="Buscar usuarios"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          placeholder="Buscar por nombre o correo…"
          className="input-base h-11 w-full min-w-0 sm:h-9 sm:w-72"
        />
      </div>

      {consultaUsuarios.isPending && (
        <p className="text-sm text-slate-500">Cargando usuarios…</p>
      )}
      {consultaUsuarios.isError && (
        <p role="alert" className="text-sm text-red-600">
          No se pudo cargar la lista de usuarios.
        </p>
      )}

      {/* Tabla escritorio */}
      <div className="hidden overflow-auto rounded-md border sm:block">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-[11px] uppercase text-slate-500">
            <tr>
              <th scope="col" className="text-left p-3">
                Usuario
              </th>
              <th scope="col" className="text-left p-3">
                Roles
              </th>
              <th scope="col" className="text-left p-3">
                Vínculo
              </th>
              <th scope="col" className="text-left p-3">
                Estado
              </th>
              <th scope="col" className="text-right p-3">
                Acciones
              </th>
            </tr>
          </thead>
          <tbody>
            {filtrados.map((u) => (
              <tr key={u.id_usuario} className="border-t hover:bg-slate-50">
                <td className="p-3">
                  <p className="font-medium">{u.nombre ?? u.correo}</p>
                  <p className="text-xs text-slate-500">{u.correo}</p>
                </td>
                <td className="p-3">
                  <div className="flex flex-wrap gap-1">
                    {u.roles.map((r) => (
                      <span
                        key={r}
                        className="text-xs px-2 py-0.5 rounded border bg-white"
                      >
                        {rotuloRol(r)}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="p-3 text-xs">
                  {u.concesionario?.nombre ??
                    (u.aliados.length > 0
                      ? u.aliados.map((a) => a.nombre).join(', ')
                      : '—')}
                </td>
                <td className="p-3">
                  <span
                    className={`text-[11px] px-2 py-0.5 rounded-full border ${
                      u.estado === 'activo'
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                        : 'bg-red-50 text-red-700 border-red-200'
                    }`}
                  >
                    {estadoRotulo(u.estado)}
                  </span>
                  {u.requiere_cambio_password && (
                    <span className="ml-1 text-[11px] text-amber-600">
                      clave temporal
                    </span>
                  )}
                </td>
                <td className="p-3">
                  <div className="flex justify-end gap-1">
                    <button
                      type="button"
                      onClick={() => abrirEditar(u)}
                      aria-label={`Editar ${u.nombre ?? u.correo}`}
                      title="Editar"
                      className="h-7 w-7 grid place-items-center rounded border"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    {u.roles.includes('asesor') && (
                      <button
                        type="button"
                        onClick={() => setHistorialDe(u)}
                        aria-label={`Historial de ${u.nombre ?? u.correo}`}
                        title="Historial de la ficha"
                        className="h-7 w-7 grid place-items-center rounded border"
                      >
                        <History className="h-3.5 w-3.5" />
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => {
                        setResetDe(u)
                        setNuevaClave('')
                      }}
                      aria-label={`Restablecer clave de ${u.nombre ?? u.correo}`}
                      title="Restablecer clave"
                      className="h-7 w-7 grid place-items-center rounded border"
                    >
                      <KeyRound className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => mutEstado.mutate(u)}
                      aria-label={`${u.estado === 'activo' ? 'Desactivar' : 'Activar'} ${u.nombre ?? u.correo}`}
                      title={u.estado === 'activo' ? 'Desactivar' : 'Activar'}
                      className="h-7 w-7 grid place-items-center rounded border"
                    >
                      {u.estado === 'activo' ? (
                        <UserX className="h-3.5 w-3.5" />
                      ) : (
                        <UserCheck className="h-3.5 w-3.5" />
                      )}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Tarjetas móvil */}
      <div className="space-y-3 sm:hidden">
        {filtrados.map((u) => (
          <article
            key={u.id_usuario}
            className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
          >
            <div className="flex min-w-0 items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold">
                  {u.nombre ?? u.correo}
                </p>
                <p className="mt-1 break-all text-xs text-slate-500">
                  {u.correo}
                </p>
              </div>
              <span
                className={`shrink-0 rounded-full border px-2.5 py-1 text-[11px] ${
                  u.estado === 'activo'
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                    : 'border-red-200 bg-red-50 text-red-700'
                }`}
              >
                {estadoRotulo(u.estado)}
              </span>
            </div>
            <dl className="mt-4 grid grid-cols-2 gap-3 border-t border-slate-100 pt-3">
              <div>
                <dt className="text-[10px] font-medium uppercase tracking-wide text-slate-500">
                  Roles
                </dt>
                <dd className="mt-1 text-xs font-medium">
                  {u.roles.map(rotuloRol).join(', ')}
                </dd>
              </div>
              <div className="min-w-0">
                <dt className="text-[10px] font-medium uppercase tracking-wide text-slate-500">
                  Vínculo
                </dt>
                <dd className="mt-1 truncate text-xs font-medium">
                  {u.concesionario?.nombre ??
                    (u.aliados.length > 0
                      ? u.aliados.map((a) => a.nombre).join(', ')
                      : '—')}
                </dd>
              </div>
            </dl>
            <div className="mt-3 flex gap-2 border-t border-slate-100 pt-3">
              <button
                type="button"
                onClick={() => abrirEditar(u)}
                className="flex h-11 flex-1 items-center justify-center gap-2 rounded-lg border text-xs font-medium"
              >
                <Pencil className="h-4 w-4" /> Editar
              </button>
              {u.roles.includes('asesor') && (
                <button
                  type="button"
                  onClick={() => setHistorialDe(u)}
                  aria-label={`Historial de ${u.nombre ?? u.correo}`}
                  className="grid h-11 w-11 place-items-center rounded-lg border"
                >
                  <History className="h-4 w-4" />
                </button>
              )}
              <button
                type="button"
                onClick={() => {
                  setResetDe(u)
                  setNuevaClave('')
                }}
                aria-label={`Restablecer clave de ${u.nombre ?? u.correo}`}
                className="grid h-11 w-11 place-items-center rounded-lg border"
              >
                <KeyRound className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => mutEstado.mutate(u)}
                aria-label={`${u.estado === 'activo' ? 'Desactivar' : 'Activar'} ${u.nombre ?? u.correo}`}
                className="grid h-11 w-11 place-items-center rounded-lg border text-slate-500 hover:bg-red-50 hover:text-red-600"
              >
                {u.estado === 'activo' ? (
                  <UserX className="h-4 w-4" />
                ) : (
                  <UserCheck className="h-4 w-4" />
                )}
              </button>
            </div>
          </article>
        ))}
      </div>

      {/* Modal crear/editar */}
      {modalAbierto && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-0 backdrop-blur-sm sm:items-center sm:p-4">
          <div
            ref={modalRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="usuario-modal-titulo"
            onKeyDown={(event) => {
              if (event.key === 'Escape') setModalAbierto(false)
            }}
            className="flex max-h-[92dvh] w-full max-w-[520px] flex-col overflow-hidden rounded-t-2xl border bg-white shadow-2xl sm:max-h-[calc(100dvh-2rem)] sm:rounded-xl"
          >
            <div className="flex shrink-0 items-center justify-between border-b p-4 sm:p-5">
              <div>
                <h3 id="usuario-modal-titulo" className="font-semibold text-sm">
                  {editando ? 'Editar usuario' : 'Nuevo usuario'}
                </h3>
                <p className="text-xs text-slate-500">
                  {editando
                    ? `Editando a ${editando.correo}`
                    : 'Acceso con clave temporal'}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setModalAbierto(false)}
                aria-label="Cerrar diálogo"
                className="grid h-11 w-11 place-items-center rounded-full hover:bg-slate-100 sm:h-8 sm:w-8"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <form onSubmit={guardar}>
              <div className="grid gap-4 overflow-y-auto p-4 sm:p-5">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <CampoEntrada
                    label="Nombre completo *"
                    value={form.nombre}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, nombre: e.target.value }))
                    }
                    required
                    minLength={3}
                  />
                  <CampoEntrada
                    label="Correo *"
                    type="email"
                    value={form.correo}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, correo: e.target.value }))
                    }
                    disabled={editando != null}
                    required
                  />
                </div>

                {!editando && (
                  <CampoEntrada
                    label="Clave temporal *"
                    type="text"
                    value={form.contrasena}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, contrasena: e.target.value }))
                    }
                    minLength={8}
                    required
                    autoComplete="off"
                  />
                )}

                <fieldset>
                  <legend className="label-base">Roles *</legend>
                  <div className="flex flex-wrap gap-2">
                    {(opciones?.roles ?? []).map((rol) => (
                      <label
                        key={rol.id_rol}
                        className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-xs ${
                          form.roles.includes(rol.nombre)
                            ? 'border-brand-500 bg-brand-50'
                            : ''
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={form.roles.includes(rol.nombre)}
                          onChange={() => alternarRol(rol.nombre)}
                        />
                        {rotuloRol(rol.nombre)}
                      </label>
                    ))}
                  </div>
                </fieldset>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  {(form.roles.includes('asesor') ||
                    form.roles.includes('concesionario')) && (
                    <div>
                      <label className="label-base" htmlFor="usuario-sede">
                        {form.roles.includes('concesionario') &&
                        !form.roles.includes('asesor')
                          ? 'Concesionario que administra *'
                          : 'Concesionario del asesor *'}
                      </label>
                      <select
                        id="usuario-sede"
                        className="input-base"
                        value={form.idConcesionario}
                        onChange={(e) =>
                          setForm((f) => ({
                            ...f,
                            idConcesionario: e.target.value,
                          }))
                        }
                        required
                      >
                        <option value="">Seleccionar…</option>
                        {(opciones?.concesionarios ?? []).map((c) => (
                          <option
                            key={c.id_concesionario}
                            value={c.id_concesionario}
                          >
                            {c.nombre}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                  {form.roles.includes('aliado') && (
                    <div>
                      <label className="label-base" htmlFor="usuario-aliado">
                        Aliado financiero *
                      </label>
                      <select
                        id="usuario-aliado"
                        className="input-base"
                        value={form.idAliado}
                        onChange={(e) =>
                          setForm((f) => ({
                            ...f,
                            idAliado: e.target.value,
                          }))
                        }
                        required
                      >
                        <option value="">Seleccionar…</option>
                        {(opciones?.aliados ?? []).map((a) => (
                          <option key={a.id_aliado} value={a.id_aliado}>
                            {a.nombre}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                  {form.roles.includes('asesor') && (
                    <>
                      <CampoEntrada
                        label="Cédula del asesor *"
                        value={form.cedula}
                        onChange={(e) =>
                          setForm((f) => ({ ...f, cedula: e.target.value }))
                        }
                        inputMode="numeric"
                        required
                      />
                      <CampoEntrada
                        label="Celular del asesor *"
                        type="tel"
                        value={form.telefono}
                        onChange={(e) =>
                          setForm((f) => ({
                            ...f,
                            telefono: e.target.value,
                          }))
                        }
                        required
                      />
                      <div>
                        <label className="label-base" htmlFor="usuario-ciudad">
                          Ciudad
                        </label>
                        <input
                          id="usuario-ciudad"
                          className="input-base bg-slate-50 text-slate-500"
                          value={
                            opciones?.concesionarios.find(
                              (c) =>
                                String(c.id_concesionario) ===
                                form.idConcesionario,
                            )?.ciudad ?? ''
                          }
                          readOnly
                          disabled
                          aria-label="Ciudad de la sede (automática)"
                        />
                        <p className="mt-1 text-[11px] text-slate-400">
                          La ciudad es la del concesionario elegido.
                        </p>
                      </div>
                    </>
                  )}
                  {editando && (
                    <div>
                      <label className="label-base" htmlFor="usuario-estado">
                        Estado
                      </label>
                      <select
                        id="usuario-estado"
                        className="input-base"
                        value={form.estado}
                        onChange={(e) =>
                          setForm((f) => ({ ...f, estado: e.target.value }))
                        }
                      >
                        {ESTADOS.map((e) => (
                          <option key={e.valor} value={e.valor}>
                            {e.rotulo}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>

                {errorForm && (
                  <p role="alert" className="text-sm text-red-600">
                    {errorForm}
                  </p>
                )}
              </div>
              <div className="flex shrink-0 justify-end gap-2 border-t p-4 sm:p-5">
                <button
                  type="button"
                  onClick={() => setModalAbierto(false)}
                  className="btn-secondary"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                  disabled={mutGuardar.isPending}
                >
                  {mutGuardar.isPending
                    ? 'Guardando…'
                    : editando
                      ? 'Guardar cambios'
                      : 'Crear usuario'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal restablecer clave */}
      {resetDe && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-0 backdrop-blur-sm sm:items-center sm:p-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="reset-modal-titulo"
            className="w-full max-w-[420px] rounded-t-2xl border bg-white shadow-2xl sm:rounded-xl"
          >
            <div className="flex items-center justify-between border-b p-4">
              <h3 id="reset-modal-titulo" className="font-semibold text-sm">
                Restablecer clave
              </h3>
              <button
                type="button"
                onClick={() => setResetDe(null)}
                aria-label="Cerrar diálogo"
                className="grid h-11 w-11 place-items-center rounded-full hover:bg-slate-100 sm:h-8 sm:w-8"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="grid gap-4 p-4">
              <p className="text-xs text-slate-500">
                Nueva clave temporal para <b>{resetDe.correo}</b>. La cuenta
                queda desbloqueada y el usuario deberá cambiarla al ingresar.
              </p>
              <CampoEntrada
                label="Nueva clave temporal"
                type="text"
                value={nuevaClave}
                onChange={(e) => setNuevaClave(e.target.value)}
                minLength={8}
                autoComplete="off"
              />
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setResetDe(null)}
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  className="btn-primary"
                  disabled={nuevaClave.length < 8 || mutReset.isPending}
                  onClick={() => mutReset.mutate()}
                >
                  {mutReset.isPending ? 'Restableciendo…' : 'Restablecer'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal historial de la ficha del asesor */}
      {historialDe && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-0 backdrop-blur-sm sm:items-center sm:p-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="historial-modal-titulo"
            className="flex max-h-[80dvh] w-full max-w-[480px] flex-col overflow-hidden rounded-t-2xl border bg-white shadow-2xl sm:rounded-xl"
          >
            <div className="flex shrink-0 items-center justify-between border-b p-4">
              <div>
                <h3
                  id="historial-modal-titulo"
                  className="font-semibold text-sm"
                >
                  Historial de la cuenta
                </h3>
                <p className="text-xs text-slate-500">
                  {historialDe.correo} — cada cambio de la persona detrás del
                  correo queda registrado.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setHistorialDe(null)}
                aria-label="Cerrar diálogo"
                className="grid h-11 w-11 place-items-center rounded-full hover:bg-slate-100 sm:h-8 sm:w-8"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="overflow-y-auto p-4">
              {consultaHistorial.isPending && (
                <p className="text-sm text-slate-500">Cargando historial…</p>
              )}
              {consultaHistorial.isError && (
                <p role="alert" className="text-sm text-red-600">
                  No se pudo cargar el historial.
                </p>
              )}
              {consultaHistorial.data &&
                consultaHistorial.data.length === 0 && (
                  <p className="text-sm text-slate-500">
                    Sin cambios registrados.
                  </p>
                )}
              <ol className="space-y-3">
                {(consultaHistorial.data ?? []).map((fila, i) => (
                  <li
                    key={i}
                    className="rounded-lg border border-slate-200 p-3 text-xs"
                  >
                    <div className="flex justify-between gap-2 text-slate-500">
                      <span>
                        {new Date(fila.fecha).toLocaleString('es-CO')}
                      </span>
                      <span>{fila.nombre_quien ?? '—'}</span>
                    </div>
                    <dl className="mt-2 space-y-1">
                      {Object.entries(fila.cambios).map(([campo, cambio]) => (
                        <div key={campo} className="flex gap-2">
                          <dt className="w-20 shrink-0 font-medium text-slate-600">
                            {ROTULO_CAMBIO[campo] ?? campo}
                          </dt>
                          <dd className="min-w-0 text-slate-700">
                            {String(cambio.antes ?? '—')}
                            <span aria-hidden="true"> → </span>
                            <b>{String(cambio.despues ?? '—')}</b>
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
