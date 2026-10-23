import { env } from '../../../env'
import { obtenerToken } from '../../../shared/lib/sesion'
import type { RolSesion, UsuarioSesion } from '../../../shared/lib/sesion'

const API = import.meta.env.DEV ? '' : env.VITE_API_URL.replace(/\/$/, '')

export interface UsuarioAutenticado {
  correo: string
  nombre: string
  /** Rol principal del panel: 'admin' | 'asesor' | 'aliado'. */
  rol: RolSesion
  roles: RolSesion[]
  concesionario: { id_concesionario: number; nombre: string } | null
  /** El admin entregó una clave temporal: el panel fuerza el cambio. */
  requiere_cambio_password?: boolean
}

export interface RespuestaLogin {
  access_token: string
  refresh_token?: string
  token_type: string
  usuario: UsuarioAutenticado
}

export interface RespuestaRefresh {
  access_token: string
  refresh_token: string
  usuario: UsuarioSesion
}

export class ErrorAutenticacionApi extends Error {
  readonly status: number

  constructor(status: number, detalle: unknown) {
    super(
      typeof detalle === 'string'
        ? detalle
        : `No fue posible iniciar sesión (error ${status}).`,
    )
    this.name = 'ErrorAutenticacionApi'
    this.status = status
  }
}

export async function iniciarSesion(correo: string, contrasena: string) {
  const respuesta = await fetch(`${API}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ correo, contrasena }),
  })
  const cuerpo: unknown = await respuesta.json().catch(() => null)

  if (!respuesta.ok) {
    const detalle =
      cuerpo && typeof cuerpo === 'object' && 'detail' in cuerpo
        ? cuerpo.detail
        : `No fue posible iniciar sesión (error ${respuesta.status}).`
    throw new ErrorAutenticacionApi(respuesta.status, detalle)
  }

  if (
    !cuerpo ||
    typeof cuerpo !== 'object' ||
    !('access_token' in cuerpo) ||
    typeof cuerpo.access_token !== 'string' ||
    !cuerpo.access_token ||
    !('usuario' in cuerpo) ||
    !cuerpo.usuario ||
    typeof cuerpo.usuario !== 'object' ||
    !('correo' in cuerpo.usuario) ||
    typeof cuerpo.usuario.correo !== 'string' ||
    !('nombre' in cuerpo.usuario) ||
    typeof cuerpo.usuario.nombre !== 'string' ||
    !('rol' in cuerpo.usuario) ||
    typeof cuerpo.usuario.rol !== 'string'
  ) {
    throw new Error(
      'La API devolvió una respuesta de inicio de sesión inválida.',
    )
  }

  return cuerpo as RespuestaLogin
}

/** Cambio de clave propio: resuelve la temporal que el admin entrega. */
export async function cambiarClave(
  contrasenaActual: string,
  contrasenaNueva: string,
): Promise<UsuarioAutenticado> {
  const respuesta = await fetch(`${API}/api/auth/cambiar-clave`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(obtenerToken() ? { Authorization: `Bearer ${obtenerToken()}` } : {}),
    },
    body: JSON.stringify({
      contrasena_actual: contrasenaActual,
      contrasena_nueva: contrasenaNueva,
    }),
  })
  const cuerpo: unknown = await respuesta.json().catch(() => null)

  if (!respuesta.ok) {
    const detalle =
      cuerpo && typeof cuerpo === 'object' && 'detail' in cuerpo
        ? cuerpo.detail
        : `No fue posible cambiar la contraseña (error ${respuesta.status}).`
    throw new ErrorAutenticacionApi(respuesta.status, detalle)
  }
  return cuerpo as UsuarioAutenticado
}

/* ---------- Refresh token: rotación y logout efectivo ---------- */

/** POST /auth/refresh con el refresh opaco: devuelve par nuevo y la
 * sesión de usuario actualizada. 401 = sesión muerta (re-login). */
export async function refrescarSesion(
  refreshToken: string,
): Promise<RespuestaRefresh> {
  const respuesta = await fetch(`${API}/api/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  })
  const cuerpo: unknown = await respuesta.json().catch(() => null)
  if (!respuesta.ok) {
    throw new ErrorAutenticacionApi(respuesta.status, null)
  }
  if (
    !cuerpo ||
    typeof cuerpo !== 'object' ||
    !('access_token' in cuerpo) ||
    typeof cuerpo.access_token !== 'string' ||
    !('refresh_token' in cuerpo) ||
    typeof cuerpo.refresh_token !== 'string'
  ) {
    throw new Error('La API devolvió una respuesta de refresh inválida.')
  }
  return cuerpo as RespuestaRefresh
}

/** POST /auth/logout: revoca el refresh en servidor. Es best-effort —
 * el cliente limpia su estado aunque la llamada falle. */
export async function cerrarSesionApi(
  refreshToken: string | null,
): Promise<void> {
  if (!refreshToken) return
  try {
    await fetch(`${API}/api/auth/logout`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
  } catch {
    // Sin red: la sesión local se limpia igual; el token expira solo.
  }
}

/* ---------- Recuperación de clave ("olvidé mi contraseña") ---------- */

/** POST /auth/recuperar-clave: respuesta genérica — no revela si el
 * correo existe. */
export async function solicitarRecuperacion(correo: string): Promise<void> {
  const respuesta = await fetch(`${API}/api/auth/recuperar-clave`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ correo }),
  })
  if (!respuesta.ok) {
    throw new ErrorAutenticacionApi(
      respuesta.status,
      'No fue posible procesar la solicitud. Inténtalo de nuevo.',
    )
  }
}

/** POST /auth/restablecer-clave con el token del correo (un solo uso). */
export async function restablecerClave(
  token: string,
  contrasenaNueva: string,
): Promise<void> {
  const respuesta = await fetch(`${API}/api/auth/restablecer-clave`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, contrasena_nueva: contrasenaNueva }),
  })
  const cuerpo: unknown = await respuesta.json().catch(() => null)
  if (!respuesta.ok) {
    const detalle =
      cuerpo && typeof cuerpo === 'object' && 'detail' in cuerpo
        ? cuerpo.detail
        : 'No fue posible restablecer la contraseña.'
    throw new ErrorAutenticacionApi(respuesta.status, detalle)
  }
}
