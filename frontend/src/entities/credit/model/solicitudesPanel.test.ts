/**
 * Pruebas del mapeo estado/decisión del backend → insignia visual
 * del panel (D48: contrato de lectura del listado).
 */

import { describe, expect, it } from 'vitest'
import type { SolicitudResumenApi } from '../../../features/credit-origination/api/originacionApi'
import { estadoVisual, etiquetaSolicitud, numero } from './solicitudesPanel'

const base: SolicitudResumenApi = {
  id_solicitud: '9f9e0f52-0000-4000-8000-000000000000',
  num_solicitud: 42,
  fecha_hora: '2026-10-06T16:00:00Z',
  estado: 'creada',
  decision: null,
  nombre_cliente: 'Cliente Ficticio',
  num_cedula: '1000000001',
  tipo_documento: '1',
  ocupacion: 'empleado',
  linea_credito: null,
  destino_credito: null,
  plazo_deseado_meses: null,
  evaluacion: null,
}

describe('estadoVisual', () => {
  it('mapea decision aprobado y estados positivos a APROBADO', () => {
    expect(estadoVisual({ ...base, decision: 'aprobado' })).toBe('APROBADO')
    expect(estadoVisual({ ...base, estado: 'aprobada' })).toBe('APROBADO')
    expect(estadoVisual({ ...base, estado: 'desembolsada' })).toBe('APROBADO')
  })

  it('mapea decision rechazado y estados negativos a RECHAZADO', () => {
    expect(estadoVisual({ ...base, decision: 'rechazado' })).toBe('RECHAZADO')
    expect(estadoVisual({ ...base, estado: 'rechazada' })).toBe('RECHAZADO')
    expect(estadoVisual({ ...base, estado: 'cancelada' })).toBe('RECHAZADO')
  })

  it('las radicadas sin evaluar son PENDIENTE, no revisión', () => {
    expect(estadoVisual(base)).toBe('PENDIENTE')
    expect(estadoVisual({ ...base, estado: 'en_evaluacion' })).toBe('PENDIENTE')
  })

  it('perfil gris y en_revision siguen siendo REQUIERE_REVISION', () => {
    expect(estadoVisual({ ...base, estado: 'en_revision' })).toBe(
      'REQUIERE_REVISION',
    )
    expect(estadoVisual({ ...base, decision: 'perfil_gris' })).toBe(
      'REQUIERE_REVISION',
    )
  })

  it('en_revision prima: la solicitud sigue pendiente de comité', () => {
    expect(
      estadoVisual({ ...base, estado: 'en_revision', decision: 'rechazado' }),
    ).toBe('REQUIERE_REVISION')
  })
})

describe('etiquetaSolicitud', () => {
  it('usa el número correlativo cuando existe', () => {
    expect(etiquetaSolicitud(base)).toBe('#42')
  })

  it('cae al prefijo del UUID cuando no hay correlativo', () => {
    expect(etiquetaSolicitud({ ...base, num_solicitud: null })).toBe('9f9e0f52')
  })
})

describe('numero', () => {
  it('convierte decimales del backend a number', () => {
    expect(numero('20000000.00')).toBe(20000000)
    expect(numero('80.1600')).toBeCloseTo(80.16)
  })

  it('devuelve null ante nulos, vacíos o no numéricos', () => {
    expect(numero(null)).toBeNull()
    expect(numero(undefined)).toBeNull()
    expect(numero('')).toBeNull()
    expect(numero('abc')).toBeNull()
  })
})
