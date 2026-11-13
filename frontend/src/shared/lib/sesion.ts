/**
 * Sesión del panel: JWT emitido por POST /api/auth/login + el usuario
 * autenticado. El rol viene del backend — no hay selector de perfil.
 *
 * Roles del panel (los valida también el backend en cada request):
 * - admin: expediente completo (score, causales, auditoría, parámetros).
 * - concesionario: administrador de sede — opera todas las solicitudes
 *   de su concesionario y gestiona sus asesores; NO ve score ni
 *   causales del motor ni los parámetros globales.
 * - asesor: opera el flujo solo sobre sus propias radicaciones; NO ve
 *   score ni causales del motor (dato sensible del cliente).
 * - aliado: solo lectura, acotada a los concesionarios de su aliado.
 * - contabilidad: back-office de operaciones — bandeja de desembolsos
 *   y cargues de garantías; NO ve score ni causales del motor.
 *
 * La UI usa el rol solo para pintar: la autorización real es la API
 * (un rol manipulado en localStorage recibe 403/404 del servidor).
 */

import { useSyncExternalStore } from 'react'

export type RolSesion =
  'admin' | 'asesor' | 'aliado' | 'concesionario' | 'contabilidad'

const ROLES_PANEL: readonly RolSesion[] = [
  'admin',
  'asesor',
  'aliado',
  'concesionario',
  'contabilidad',
]

const CLAVE_TOKEN = 'uw_token'
const CLAVE_REFRESH = 'uw_refresh'
const CLAVE_USUARIO = 'uw_usuario'
const EVENTO_SESION = 'sumoto:sesion'

/* ---------- Usuario autenticado ---------- */

export interface ConcesionarioSesion {
  id_concesionario: number
  nombre: string
}

export interface UsuarioSesion {
  correo: string
  nombre: string
  rol: RolSesion
  roles: RolSesion[]
  concesionario: ConcesionarioSesion | null
  /** El admin entregó clave temporal: el guard fuerza /cambiar-clave. */
  requiere_cambio_password?: boolean
}

function esRol(valor: unknown): valor is RolSesion {
  return ROLES_PANEL.includes(valor as RolSesion)
}

/* ---------- Token ---------- */

/** JWT persistido; el backend valida firma y expiración, aquí solo se
 * guarda para adjuntarlo como Bearer y detectar expiración client-side. */
export function obtenerToken(): string | null {
  try {
    return localStorage.getItem(CLAVE_TOKEN)
  } catch {
    return null
  }
}

/** Expiración del JWT decodificada en el cliente (orientativa: el
 * servidor siempre manda). */
export function tokenExpirado(): boolean {
  const token = obtenerToken()
  if (!token) return true
  try {
    const parte = token.split('.')[1]
    const claims: unknown = JSON.parse(
      atob(parte.replace(/-/g, '+').replace(/_/g, '/')),
    )
    if (
      !claims ||
      typeof claims !== 'object' ||
      !('exp' in claims) ||
      typeof claims.exp !== 'number'
    )
      return false
    return claims.exp * 1000 <= Date.now()
  } catch {
    return false
  }
}

/** Refresh token opaco persistido (rotación en cada /auth/refresh). */
export function obtenerRefresh(): string | null {
  try {
    return localStorage.getItem(CLAVE_REFRESH)
  } catch {
    return null
  }
}

export function haySesionVigente(): boolean {
  if (obtenerUsuario() === null) return false
  // Access vigente, o uno vencido pero con refresh para renovarlo (el
  // primer request de la página lo rota vía el cliente de API).
  return (
    (obtenerToken() !== null && !tokenExpirado()) || obtenerRefresh() !== null
  )
}

/** Persiste tokens + usuario devueltos por el login real. */
export function guardarSesion(
  accessToken: string,
  usuario: UsuarioSesion,
  refreshToken?: string | null,
): void {
  try {
    // Claves del sistema demo anterior: si quedan, no deben leerse más.
    localStorage.removeItem('uw_auth')
    localStorage.removeItem('uw_rol')
    localStorage.setItem(CLAVE_TOKEN, accessToken)
    if (refreshToken) {
      localStorage.setItem(CLAVE_REFRESH, refreshToken)
    } else {
      localStorage.removeItem(CLAVE_REFRESH)
    }
    localStorage.setItem(CLAVE_USUARIO, JSON.stringify(usuario))
    // El concesionario de la sesión vive en `usuario`; se espeja en la
    // clave propia para los lectores existentes (marca del vehículo).
    if (usuario.concesionario) {
      localStorage.setItem(CLAVE_CONCESIONARIO, usuario.concesionario.nombre)
    } else {
      localStorage.removeItem(CLAVE_CONCESIONARIO)
    }
  } catch {
    // localStorage bloqueado: la sesión sigue en memoria del módulo.
  }
  window.dispatchEvent(new Event(EVENTO_SESION))
}

/* Cache del parse: `useSyncExternalStore` exige que el snapshot sea
 * estable entre renders — un objeto nuevo en cada lectura produce
 * re-render infinito. La clave es el string crudo guardado. */
let cacheCrudo: string | null = null
let cacheUsuario: UsuarioSesion | null = null

export function obtenerUsuario(): UsuarioSesion | null {
  let crudo: string | null = null
  try {
    crudo = localStorage.getItem(CLAVE_USUARIO)
  } catch {
    crudo = null
  }
  if (crudo === cacheCrudo) return cacheUsuario
  cacheCrudo = crudo
  cacheUsuario = null
  if (!crudo) return null
  try {
    const datos: unknown = JSON.parse(crudo)
    if (
      !datos ||
      typeof datos !== 'object' ||
      !('nombre' in datos) ||
      typeof datos.nombre !== 'string' ||
      !('rol' in datos) ||
      !esRol(datos.rol)
    )
      return null
    const usuario = datos as UsuarioSesion
    cacheUsuario = {
      ...usuario,
      roles: Array.isArray(usuario.roles)
        ? usuario.roles.filter(esRol)
        : [usuario.rol],
      concesionario: usuario.concesionario ?? null,
    }
    return cacheUsuario
  } catch {
    return null
  }
}

/** Tras POST /cambiar-clave: apaga el flag en la sesión guardada para
 * que el guard suelte el resto del panel (el servidor ya lo apagó). */
export function marcarClaveCambiada(): void {
  const usuario = obtenerUsuario()
  if (!usuario) return
  cacheUsuario = { ...usuario, requiere_cambio_password: false }
  try {
    localStorage.setItem(CLAVE_USUARIO, JSON.stringify(cacheUsuario))
  } catch {
    // Sin persistencia: basta el cache del módulo.
  }
  window.dispatchEvent(new Event(EVENTO_SESION))
}

/** Tras POST /auth/refresh: el par rotado reemplaza al anterior sin
 * tocar el usuario de la sesión. */
export function guardarTokens(accessToken: string, refreshToken: string): void {
  try {
    localStorage.setItem(CLAVE_TOKEN, accessToken)
    localStorage.setItem(CLAVE_REFRESH, refreshToken)
  } catch {
    // Sin persistencia: el próximo request usa lo que haya quedado.
  }
}

export function limpiarSesion(): void {
  try {
    localStorage.removeItem(CLAVE_TOKEN)
    localStorage.removeItem(CLAVE_REFRESH)
    localStorage.removeItem(CLAVE_USUARIO)
    localStorage.removeItem(CLAVE_CONCESIONARIO)
    localStorage.removeItem('uw_auth')
    localStorage.removeItem('uw_rol')
  } catch {
    // Sin persistencia que limpiar.
  }
  cacheCrudo = null
  cacheUsuario = null
  window.dispatchEvent(new Event(EVENTO_SESION))
}

/* ---------- Rol de la sesión (reactivo) ---------- */

/** Prioridad de privilegio cuando el usuario acumula varios roles.
 * El concesionario va sobre el asesor: quien administra la sede y
 * radica a la vez conserva la visión completa de la sede. */
const PRIORIDAD_ROLES: readonly RolSesion[] = [
  'admin',
  'concesionario',
  'asesor',
  'aliado',
]

/** Rol principal del usuario autenticado: el de mayor privilegio entre
 * sus roles del panel (un admin que también es asesor sigue viendo la
 * vista de administrador). Sin sesión devuelve 'aliado': la vista más
 * restrictiva. */
export function obtenerRol(): RolSesion {
  const usuario = obtenerUsuario()
  if (!usuario) return 'aliado'
  return PRIORIDAD_ROLES.find((r) => usuario.roles.includes(r)) ?? usuario.rol
}

export function esAdmin(rol: RolSesion): boolean {
  return rol === 'admin'
}

/** Puede ejecutar acciones operativas (radicar, evaluar, OTP,
 * desembolso): admin, concesionario y asesor sí; el aliado solo lee. */
export function puedeOperar(rol: RolSesion): boolean {
  return rol === 'admin' || rol === 'asesor' || rol === 'concesionario'
}

function suscribir(notificar: () => void): () => void {
  window.addEventListener(EVENTO_SESION, notificar)
  window.addEventListener('storage', notificar)
  return () => {
    window.removeEventListener(EVENTO_SESION, notificar)
    window.removeEventListener('storage', notificar)
  }
}

/** Rol reactivo: re-renderiza al iniciar/cerrar sesión. */
export function useRol(): RolSesion {
  return useSyncExternalStore(suscribir, obtenerRol)
}

/** Usuario reactivo de la sesión (nombre, correo, sede). */
export function useUsuario(): UsuarioSesion | null {
  return useSyncExternalStore(suscribir, obtenerUsuario)
}

/** Contexto visible en las cabeceras de radicación: asesor autenticado
 * y concesionario donde opera. */
export function contextoRadicacion(): { asesor: string; sede: string } {
  return {
    asesor: obtenerUsuario()?.nombre ?? 'Asesor',
    sede: obtenerConcesionario(),
  }
}

/* ---------- Concesionario de la sesión ---------- */

const CLAVE_CONCESIONARIO = 'uw_concesionario'
/** Sede de respaldo cuando el usuario no trae concesionario (admin sin
 * sede): marca inferida para precargar el vehículo del financiamiento. */
export const CONCESIONARIO_DEFECTO = 'Sumoto S.A'

/** Sede operativa: la del usuario autenticado (asesor/aliado) o el
 * respaldo local. Ya no es un dato que el cliente elija libremente. */
export function obtenerConcesionario(): string {
  const deSesion = obtenerUsuario()?.concesionario?.nombre
  if (deSesion) return deSesion
  try {
    return localStorage.getItem(CLAVE_CONCESIONARIO) || CONCESIONARIO_DEFECTO
  } catch {
    return CONCESIONARIO_DEFECTO
  }
}

/** Marca inferida del concesionario ('Bajaj Tuluá' → 'Bajaj'). */
export function marcaDeConcesionario(concesionario: string): string {
  return concesionario.trim().split(/\s+/)[0] ?? ''
}
