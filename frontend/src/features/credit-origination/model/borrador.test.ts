/**
 * Persistencia del borrador de originación: el flujo debe poder
 * reanudarse tras cerrar el navegador o perder energía, sin perder
 * el paso ni la solicitud ya radicada.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  cargarBorrador,
  guardarBorrador,
  limpiarBorrador,
  type ContextoOriginacion,
} from './borrador'

function stubLocalStorage() {
  const datos = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (k: string) => datos.get(k) ?? null,
    setItem: (k: string, v: string) => void datos.set(k, v),
    removeItem: (k: string) => void datos.delete(k),
    clear: () => datos.clear(),
  })
  return datos
}

const contexto: ContextoOriginacion = {
  validacion: {
    tipoDocumento: 'CC',
    numeroDocumento: '4372665',
    fechaNacimiento: '1991-08-15',
    nacionalidad: 'Colombia',
    multasPendientes: false,
  },
  idSolicitud: '9f9e0f52-0000-4000-8000-000000000000',
}

describe('borrador de originación', () => {
  beforeEach(() => {
    stubLocalStorage()
    limpiarBorrador()
  })

  it('no hay borrador cuando nunca se guardó', () => {
    expect(cargarBorrador()).toBeNull()
  })

  it('guarda y recupera paso, contexto e id de solicitud', () => {
    guardarBorrador(5, contexto, false)
    const borrador = cargarBorrador()
    expect(borrador).not.toBeNull()
    expect(borrador!.paso).toBe(5)
    expect(borrador!.contexto.validacion?.numeroDocumento).toBe('4372665')
    expect(borrador!.contexto.idSolicitud).toBe(contexto.idSolicitud)
    expect(borrador!.formalizacionIniciada).toBe(false)
    expect(borrador!.guardadoEn).toBeTruthy()
  })

  it('sobreescribe el avance más reciente', () => {
    guardarBorrador(3, {}, false)
    guardarBorrador(4, contexto, false)
    expect(cargarBorrador()!.paso).toBe(4)
  })

  it('limpiarBorrador elimina el guardado', () => {
    guardarBorrador(5, contexto, false)
    limpiarBorrador()
    expect(cargarBorrador()).toBeNull()
  })

  it('ignora contenido corrupto o de otra versión', () => {
    const datos = stubLocalStorage()
    datos.set('inversiones-pacifico:borrador-originacion', '{no-json')
    expect(cargarBorrador()).toBeNull()
    datos.set(
      'inversiones-pacifico:borrador-originacion',
      JSON.stringify({ version: 99, paso: 3, contexto: {} }),
    )
    expect(cargarBorrador()).toBeNull()
    datos.set(
      'inversiones-pacifico:borrador-originacion',
      JSON.stringify({
        version: 1,
        paso: 'siete',
        contexto: null,
        formalizacionIniciada: false,
        guardadoEn: '2026-10-07',
      }),
    )
    expect(cargarBorrador()).toBeNull()
  })

  it('nunca lanza errores aunque localStorage falle', () => {
    vi.stubGlobal('localStorage', {
      getItem: () => {
        throw new Error('denegado')
      },
      setItem: () => {
        throw new Error('lleno')
      },
      removeItem: () => {
        throw new Error('denegado')
      },
    })
    expect(cargarBorrador()).toBeNull()
    expect(() => guardarBorrador(2, {}, false)).not.toThrow()
    expect(() => limpiarBorrador()).not.toThrow()
  })
})
