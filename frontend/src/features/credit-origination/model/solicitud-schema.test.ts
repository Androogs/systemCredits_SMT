/**
 * Validación del formulario de solicitud: las reglas del esquema Zod
 * replican la política de captura (requeridos, no-negativos y Cámara
 * de Comercio obligatoria para independientes — causal R16).
 */

import { describe, expect, it } from 'vitest'
import { erroresSolicitud } from './solicitud-schema'
import type { DatosSolicitud } from '../ui/CrearSolicitud'

const datosValidos: DatosSolicitud = {
  lineaCredito: 'Inversiones Pacífico',
  destinoCredito: 'Financiamiento de Vehículos',
  plazoMeses: 36,
  ocupacion: 'Empleado Término Indefinido',
  empresa: 'SUMOTO SA',
  mesesContinuidad: 24,
  aniosCamara: null,
  ingresosMensuales: 4_500_000,
  egresosMensuales: 1_800_000,
}

describe('erroresSolicitud', () => {
  it('un formulario completo no tiene errores', () => {
    expect(erroresSolicitud(datosValidos)).toEqual({})
  })

  it('marca los campos obligatorios vacíos', () => {
    const errores = erroresSolicitud({
      ...datosValidos,
      ocupacion: '',
      empresa: '   ',
      ingresosMensuales: 0,
    })
    expect(errores.ocupacion).toBe('Selecciona la ocupación principal.')
    expect(errores.empresa).toBe('Ingresa la empresa o empleador.')
    expect(errores.ingresosMensuales).toBe('Ingresa los ingresos mensuales.')
  })

  it('exige Cámara de Comercio a independientes (R16)', () => {
    const errores = erroresSolicitud({
      ...datosValidos,
      ocupacion: 'Independiente',
      aniosCamara: null,
    })
    expect(errores.aniosCamara).toContain('R16')
  })

  it('independiente con años negativos ve la regla R16, no la de negativos', () => {
    const errores = erroresSolicitud({
      ...datosValidos,
      ocupacion: 'Independiente',
      aniosCamara: -2,
    })
    expect(errores.aniosCamara).toContain('R16')
  })

  it('años de Cámara negativos en otras ocupaciones', () => {
    const errores = erroresSolicitud({ ...datosValidos, aniosCamara: -1 })
    expect(errores.aniosCamara).toBe(
      'Los años de Cámara no pueden ser negativos.',
    )
  })

  it('rechaza años de Cámara no numéricos', () => {
    const errores = erroresSolicitud({
      ...datosValidos,
      aniosCamara: Number('abc'),
    })
    expect(errores.aniosCamara).toBe('Ingresa un número válido.')
  })

  it('rechaza negativos en continuidad y egresos', () => {
    const errores = erroresSolicitud({
      ...datosValidos,
      mesesContinuidad: -3,
      egresosMensuales: -1,
    })
    expect(errores.mesesContinuidad).toBe(
      'La continuidad no puede ser negativa.',
    )
    expect(errores.egresosMensuales).toBe(
      'Los egresos no pueden ser negativos.',
    )
  })
})
