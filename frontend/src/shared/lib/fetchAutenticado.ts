/**
 * fetch con sesión del panel: adjunta el Bearer, rota el refresh token
 * una vez ante 401 y reintenta; si sigue rechazado, limpia la sesión y
 * redirige al login. Todos los clientes de API autenticados lo usan
 * para que el refresh (D125) cubra la app completa, no una sola ruta.
 */

import {
  guardarTokens,
  limpiarSesion,
  obtenerRefresh,
  obtenerToken,
} from './sesion'

// Misma base que originacionApi: en dev el proxy de Vite resuelve /api.
const API = import.meta.env.DEV
  ? ''
  : (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')

/* Refresh single-flight: varios requests simultáneos con access token
 * vencido comparten una sola rotación — el refresh viejo muere al
 * usarse y dos /refresh seguidos con el mismo token darían 401. */
let refrescoEnCurso: Promise<boolean> | null = null

export function intentarRefresco(): Promise<boolean> {
  const refresh = obtenerRefresh()
  if (!refresh) return Promise.resolve(false)
  refrescoEnCurso ??= (async () => {
    try {
      const respuesta = await fetch(`${API}/api/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refresh }),
      })
      const cuerpo: unknown = await respuesta.json().catch(() => null)
      if (
        !respuesta.ok ||
        !cuerpo ||
        typeof cuerpo !== 'object' ||
        !('access_token' in cuerpo) ||
        typeof cuerpo.access_token !== 'string' ||
        !('refresh_token' in cuerpo) ||
        typeof cuerpo.refresh_token !== 'string'
      ) {
        return false
      }
      guardarTokens(cuerpo.access_token, cuerpo.refresh_token)
      return true
    } catch {
      return false
    } finally {
      refrescoEnCurso = null
    }
  })()
  return refrescoEnCurso
}

/** fetch con Bearer + una renovación de sesión ante 401. Devuelve la
 * Response cruda: el mapeo de errores queda en cada cliente. */
export async function fetchAutenticado(
  url: string,
  init?: RequestInit,
): Promise<Response> {
  const ejecutar = () => {
    const token = obtenerToken()
    const headers = new Headers(init?.headers)
    if (token) headers.set('Authorization', `Bearer ${token}`)
    return fetch(url, { ...init, headers })
  }
  let respuesta = await ejecutar()
  if (
    respuesta.status === 401 &&
    obtenerToken() &&
    (await intentarRefresco())
  ) {
    respuesta = await ejecutar()
  }
  // Sin refresh válido o rotación rechazada: la sesión murió en
  // servidor. Las rutas públicas no usan este helper.
  if (respuesta.status === 401 && obtenerToken()) {
    limpiarSesion()
    window.location.assign('/login')
  }
  return respuesta
}
