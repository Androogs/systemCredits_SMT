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
const CLAVE_NOMBRE = 'uw_nombre'
const CLAVE_SEDE = 'uw_sede'
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

/* ---------- Perfil del usuario autenticado ---------- */

const SEDE_DEFECTO = 'Palmira - Centro Interno'

export function obtenerNombre(): string {
  try {
    return localStorage.getItem(CLAVE_NOMBRE) || ''
  } catch {
    return ''
  }
}

export function guardarNombre(nombre: string): void {
  try {
    localStorage.setItem(CLAVE_NOMBRE, nombre)
  } catch {
    // Sin persistencia: solo afecta esta sesión.
  }
}

export function useNombre(): string {
  return useSyncExternalStore(suscribir, obtenerNombre)
}

export function obtenerSede(): string {
  try {
    return localStorage.getItem(CLAVE_SEDE) || SEDE_DEFECTO
  } catch {
    return SEDE_DEFECTO
  }
}

export function guardarSede(sede: string): void {
  try {
    localStorage.setItem(CLAVE_SEDE, sede)
  } catch {
    // Sin persistencia: solo afecta esta sesión.
  }
}

export function useSede(): string {
  return useSyncExternalStore(suscribir, obtenerSede)
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
