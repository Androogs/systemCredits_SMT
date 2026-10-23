/** Cliente del CRUD de usuarios (Ajustes → Usuarios y Permisos).
 * Todas las rutas son admin-only en el backend. */

import { env } from '../../../env'
import { fetchAutenticado } from '../../../shared/lib/fetchAutenticado'

const API = env.VITE_API_URL.replace(/\/$/, '')

export interface ConcesionarioOpcion {
  id_concesionario: number
  nombre: string
  /** Ciudad de la sede: la ficha del asesor la hereda (readonly en la
   * UI — no es un dato editable de la persona). */
  ciudad?: string | null
}

export interface UsuarioGestion {
  id_usuario: string
  correo: string
  nombre: string | null
  estado: string
  roles: string[]
  concesionario: ConcesionarioOpcion | null
  aliados: { id_aliado: number; nombre: string }[]
  /** Ficha de la persona detrás del correo (solo rol asesor). */
  cedula?: string | null
  telefono?: string | null
  requiere_cambio_password: boolean
  fecha_ultimo_acceso: string | null
  bloqueado_hasta: string | null
}

export interface AsesorHistorial {
  /** Un renglón por edición de la ficha: qué campo, de qué a cuál,
   * cuándo y quién lo hizo. */
  fecha: string
  cambios: Record<string, { antes: unknown; despues: unknown }>
  nombre_quien: string | null
}

export interface OpcionesUsuario {
  roles: { id_rol: number; nombre: string }[]
  concesionarios: ConcesionarioOpcion[]
  aliados: { id_aliado: number; nombre: string }[]
  asesores: {
    id_asesor: number
    nombre: string
    id_concesionario: number | null
  }[]
}

export interface CrearUsuarioPayload {
  correo: string
  nombre: string
  contrasena: string
  roles: string[]
  id_concesionario?: number | null
  id_aliado?: number | null
  /** Ficha del asesor (obligatoria cuando el rol es asesor). */
  cedula?: string | null
  telefono?: string | null
}

export interface ActualizarUsuarioPayload {
  nombre?: string
  estado?: string
  roles?: string[]
  id_concesionario?: number | null
  id_aliado?: number | null
  cedula?: string | null
  telefono?: string | null
}

export class ErrorUsuariosApi extends Error {
  readonly status: number

  constructor(status: number, detalle: unknown) {
    super(
      typeof detalle === 'string'
        ? detalle
        : JSON.stringify(detalle) || `Error HTTP ${status}`,
    )
    this.name = 'ErrorUsuariosApi'
    this.status = status
  }
}

async function request<T>(ruta: string, init?: RequestInit): Promise<T> {
  const respuesta = await fetchAutenticado(`${API}${ruta}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  const cuerpo: unknown = await respuesta.json().catch(() => null)

  if (!respuesta.ok) {
    const detalle =
      cuerpo && typeof cuerpo === 'object' && 'detail' in cuerpo
        ? cuerpo.detail
        : (cuerpo ?? `Error HTTP ${respuesta.status}`)
    throw new ErrorUsuariosApi(respuesta.status, detalle)
  }
  return cuerpo as T
}

export function listarUsuarios() {
  return request<UsuarioGestion[]>('/api/usuarios')
}

export function obtenerOpcionesUsuario() {
  return request<OpcionesUsuario>('/api/usuarios/opciones')
}

export function crearUsuario(payload: CrearUsuarioPayload) {
  return request<UsuarioGestion>('/api/usuarios', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function actualizarUsuario(
  idUsuario: string,
  payload: ActualizarUsuarioPayload,
) {
  return request<UsuarioGestion>(
    `/api/usuarios/${encodeURIComponent(idUsuario)}`,
    { method: 'PUT', body: JSON.stringify(payload) },
  )
}

export function restablecerClave(idUsuario: string, contrasena: string) {
  return request<void>(
    `/api/usuarios/${encodeURIComponent(idUsuario)}/restablecer-clave`,
    { method: 'POST', body: JSON.stringify({ contrasena }) },
  )
}

export function obtenerHistorialUsuario(idUsuario: string) {
  return request<AsesorHistorial[]>(
    `/api/usuarios/${encodeURIComponent(idUsuario)}/historial`,
  )
}
