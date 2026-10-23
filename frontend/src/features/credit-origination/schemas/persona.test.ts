import { describe, expect, it } from 'vitest'
import {
  correoSchema,
  datosPersonalesSchema,
  telefonoSchema,
  validacionInicialSchema,
} from './persona'

const validacionValida = {
  numeroDocumento: '1032448900',
  fechaNacimiento: '1990-05-15',
  multas: 'no' as const,
}

const datosRevisadosValidos = {
  nombres: 'CARLOS MARIO',
  apellidos: 'RESTREPO ALVAREZ',
  numeroIdentificacion: '1.032.448.900',
  sexo: 'Masculino (M)',
  fechaNacimiento: '1991-08-15',
  lugarNacimiento: 'Medellín, Antioquia',
  fechaExpedicion: '2009-08-18',
  ciudadExpedicion: 'Palmira, Valle del Cauca',
}

describe('validacionInicialSchema', () => {
  it('acepta datos válidos', () => {
    expect(validacionInicialSchema.safeParse(validacionValida).success).toBe(
      true,
    )
  })

  it('rechaza cédula con formato inválido', () => {
    const r = validacionInicialSchema.safeParse({
      ...validacionValida,
      numeroDocumento: '12345',
    })
    expect(r.success).toBe(false)
  })

  it('distingue fecha vacía de edad fuera de rango', () => {
    const vacia = validacionInicialSchema.safeParse({
      ...validacionValida,
      fechaNacimiento: '',
    })
    const fuera = validacionInicialSchema.safeParse({
      ...validacionValida,
      fechaNacimiento: '2015-01-01',
    })
    expect(vacia.success).toBe(false)
    expect(fuera.success).toBe(false)
    if (!vacia.success)
      expect(vacia.error.issues[0].message).toContain('Ingresa la fecha')
    if (!fuera.success)
      expect(fuera.error.issues[0].message).toContain('entre 18 y 65')
  })

  it('exige responder la pregunta de multas', () => {
    const r = validacionInicialSchema.safeParse({
      ...validacionValida,
      multas: undefined,
    })
    expect(r.success).toBe(false)
  })
})

describe('datosPersonalesSchema', () => {
  it('acepta los datos revisados del OCR', () => {
    expect(datosPersonalesSchema.safeParse(datosRevisadosValidos).success).toBe(
      true,
    )
  })

  it('normaliza el número de identificación con puntos', () => {
    const r = datosPersonalesSchema.safeParse({
      ...datosRevisadosValidos,
      numeroIdentificacion: '12.34',
    })
    expect(r.success).toBe(false)
  })

  it('rechaza fecha de expedición anterior al nacimiento', () => {
    const r = datosPersonalesSchema.safeParse({
      ...datosRevisadosValidos,
      fechaExpedicion: '1985-01-01',
    })
    expect(r.success).toBe(false)
    if (!r.success)
      expect(r.error.issues.some((i) => i.path[0] === 'fechaExpedicion')).toBe(
        true,
      )
  })

  it('rechaza fecha de nacimiento menor de edad', () => {
    const r = datosPersonalesSchema.safeParse({
      ...datosRevisadosValidos,
      fechaNacimiento: '2015-01-01',
    })
    expect(r.success).toBe(false)
  })

  it('exige celular de 10 dígitos y correo válido', () => {
    expect(telefonoSchema.safeParse('3001234567').success).toBe(true)
    expect(telefonoSchema.safeParse('300123').success).toBe(false)
    expect(telefonoSchema.safeParse('300 123 4567').success).toBe(false)
    expect(correoSchema.safeParse('carlos@correo.com').success).toBe(true)
    expect(correoSchema.safeParse('no-es-correo').success).toBe(false)
  })
})
