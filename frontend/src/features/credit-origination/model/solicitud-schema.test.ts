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
  plazoMeses: 24,
  ocupacion: 'Empleado',
  tipoContrato: 'Indefinido',
  subtipoIndependiente: '',
  empresa: 'SUMOTO SA',
  mesesContinuidad: 24,
  aniosCamara: null,
  ingresosMensuales: 4_500_000,
  entidadPagadora: '',
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
      subtipoIndependiente: 'Profesional independiente',
      aniosCamara: null,
    })
    expect(errores.aniosCamara).toContain('R16')
  })

  it('independiente con años negativos ve la regla R16, no la de negativos', () => {
    const errores = erroresSolicitud({
      ...datosValidos,
      ocupacion: 'Independiente',
      subtipoIndependiente: 'Comerciante independiente',
      aniosCamara: -2,
    })
    expect(errores.aniosCamara).toContain('R16')
  })

  it('acepta Fuerzas Militares como ocupación válida', () => {
    const errores = erroresSolicitud({
      ...datosValidos,
      ocupacion: 'Fuerzas Militares',
      tipoContrato: '',
      entidadPagadora: 'Ejército Nacional',
    })
    expect(errores.ocupacion).toBeUndefined()
  })

  it('exige tipo de contrato cuando la ocupación es Empleado', () => {
    const errores = erroresSolicitud({
      ...datosValidos,
      tipoContrato: '',
    })
    expect(errores.tipoContrato).toBe(
      'Selecciona el tipo de contrato del empleado.',
    )
  })

  it('el tipo de contrato no se exige a Pensionado ni Independiente', () => {
    expect(
      erroresSolicitud({
        ...datosValidos,
        ocupacion: 'Pensionado',
        tipoContrato: '',
        entidadPagadora: 'Colpensiones',
      }).tipoContrato,
    ).toBeUndefined()
    expect(
      erroresSolicitud({
        ...datosValidos,
        ocupacion: 'Independiente',
        tipoContrato: '',
        subtipoIndependiente: 'Profesional independiente',
        aniosCamara: 3,
      }).tipoContrato,
    ).toBeUndefined()
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

  it('rechaza continuidad negativa y no pide meses a no empleados', () => {
    const erroresEmpleado = erroresSolicitud({
      ...datosValidos,
      mesesContinuidad: -3,
    })
    expect(erroresEmpleado.mesesContinuidad).toBe(
      'La continuidad no puede ser negativa.',
    )

    const erroresPensionado = erroresSolicitud({
      ...datosValidos,
      ocupacion: 'Pensionado',
      mesesContinuidad: -3,
      entidadPagadora: 'Colpensiones',
    })
    expect(erroresPensionado.mesesContinuidad).toBe(
      'La continuidad no puede ser negativa.',
    )
    expect(erroresPensionado.entidadPagadora).toBeUndefined()
  })

  it('exige entidad pagadora a Pensionado y Fuerzas Militares', () => {
    const erroresPensionado = erroresSolicitud({
      ...datosValidos,
      ocupacion: 'Pensionado',
      tipoContrato: '',
      entidadPagadora: '',
    })
    expect(erroresPensionado.entidadPagadora).toBe(
      'Selecciona la entidad pagadora o institución.',
    )

    const erroresFuerzas = erroresSolicitud({
      ...datosValidos,
      ocupacion: 'Fuerzas Militares',
      tipoContrato: '',
      entidadPagadora: '',
    })
    expect(erroresFuerzas.entidadPagadora).toBe(
      'Selecciona la entidad pagadora o institución.',
    )
  })

  it('exige subtipo de independiente', () => {
    const errores = erroresSolicitud({
      ...datosValidos,
      ocupacion: 'Independiente',
      subtipoIndependiente: '',
      aniosCamara: 3,
    })
    expect(errores.subtipoIndependiente).toBe(
      'Selecciona el tipo de independiente.',
    )
  })
})
