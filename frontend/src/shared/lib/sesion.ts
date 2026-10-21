/**
 * Rol de la sesión del panel. La autenticación real (JWT + roles en
 * backend) está pendiente; mientras tanto el perfil se elige al
 * ingresar y se puede alternar desde el menú lateral para comparar
 * la vista de asesor vs administrador.
 *
 * - asesor: opera el flujo y ve decisiones/montos; NO ve score ni
 *   causales del motor (dato sensible del cliente).
 * - administrador: vista completa, incluida trazabilidad y auditoría.
 */

import { useSyncExternalStore } from 'react'

export type RolSesion = 'asesor' | 'administrador'

const CLAVE_ROL = 'uw_rol'
const EVENTO_ROL = 'inversiones-pacifico:rol'

export function obtenerRol(): RolSesion {
  try {
    return localStorage.getItem(CLAVE_ROL) === 'asesor'
      ? 'asesor'
      : 'administrador'
  } catch {
    return 'administrador'
  }
}

export function guardarRol(rol: RolSesion): void {
  try {
    localStorage.setItem(CLAVE_ROL, rol)
  } catch {
    // localStorage bloqueado: la vista sigue funcionando en memoria.
  }
  window.dispatchEvent(new Event(EVENTO_ROL))
}

function suscribir(notificar: () => void): () => void {
  window.addEventListener(EVENTO_ROL, notificar)
  window.addEventListener('storage', notificar)
  return () => {
    window.removeEventListener(EVENTO_ROL, notificar)
    window.removeEventListener('storage', notificar)
  }
}

/** Rol reactivo: re-renderiza al cambiar el perfil desde el menú. */
export function useRol(): RolSesion {
  return useSyncExternalStore(suscribir, obtenerRol)
}

/* ---------- Usuario autenticado ---------- */

const CLAVE_USUARIO = 'uw_usuario'

export interface UsuarioSesion {
  nombre: string
  correo: string
  rol: string
}

/** Persiste el usuario devuelto por POST /api/auth/login para que las
 * cabeceras muestren al asesor real en vez de datos quemados. */
export function guardarUsuario(usuario: UsuarioSesion): void {
  try {
    localStorage.setItem(CLAVE_USUARIO, JSON.stringify(usuario))
  } catch {
    // localStorage bloqueado: la sesión sigue funcionando en memoria.
  }
}

export function obtenerUsuario(): UsuarioSesion | null {
  try {
    const crudo = localStorage.getItem(CLAVE_USUARIO)
    if (!crudo) return null
    const datos: unknown = JSON.parse(crudo)
    if (
      !datos ||
      typeof datos !== 'object' ||
      !('nombre' in datos) ||
      typeof datos.nombre !== 'string'
    )
      return null
    return datos as UsuarioSesion
  } catch {
    return null
  }
}

export function limpiarUsuario(): void {
  try {
    localStorage.removeItem(CLAVE_USUARIO)
  } catch {
    // Sin persistencia que limpiar.
  }
}

/** Contexto visible en las cabeceras de radicación: asesor autenticado
 * y concesionario donde opera. */
export function contextoRadicacion(): { asesor: string; sede: string } {
  return {
    asesor: obtenerUsuario()?.nombre ?? 'Asesor',
    sede: obtenerConcesionario(),
  }
}

/* ---------- Concesionario del asesor ---------- */

const CLAVE_CONCESIONARIO = 'uw_concesionario'
/** Dealer donde opera el asesor de la cuenta; la marca del vehículo se
 * toma de aquí al capturar la financiación. */
export const CONCESIONARIO_DEFECTO = 'Suzuki Palmira'

export function obtenerConcesionario(): string {
  try {
    return localStorage.getItem(CLAVE_CONCESIONARIO) || CONCESIONARIO_DEFECTO
  } catch {
    return CONCESIONARIO_DEFECTO
  }
}

export function guardarConcesionario(nombre: string): void {
  try {
    localStorage.setItem(CLAVE_CONCESIONARIO, nombre)
  } catch {
    // Sin persistencia: solo afecta esta sesión.
  }
}

/** Marca inferida del concesionario ('Bajaj Tuluá' → 'Bajaj'). */
export function marcaDeConcesionario(concesionario: string): string {
  return concesionario.trim().split(/\s+/)[0] ?? ''
}
