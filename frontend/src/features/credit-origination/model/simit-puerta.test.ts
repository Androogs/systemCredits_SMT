/**
 * Lógica de la puerta SIMIT (paso 3): llave de la consulta e
 * interpretación de la respuesta del endpoint.
 *
 * El componente dispara la consulta solo al montar (habeas +
 * documento) y la repite cuando la llave cambia; estas pruebas cubren
 * esa lógica sin montar DOM:
 * - autocompletado Sí/No según la respuesta,
 * - la llave que invalida y re-dispara al cambiar el documento,
 * - el fallback a la verificación manual (popup) cuando el proveedor
 *   no responde o la integración está deshabilitada.
 * `mensaje` no nulo es además lo que bloquea el toggle Sí/No (ya hay
 * respuesta del backend); el fallback manual lo deja libre.
 */

import { describe, expect, it } from 'vitest'
import {
  claveSimit,
  documentoCompletoSimit,
  interpretarSimit,
} from './simit-puerta'
import type { SimitConsultaResultado } from '../api/originacionApi'

const conDeuda: SimitConsultaResultado = {
  habilitado: true,
  tiene_multas: true,
  total_deuda: 1_983_733,
  total_items: 2,
  origen: 'portal',
}

const pazYSalvo: SimitConsultaResultado = {
  habilitado: true,
  tiene_multas: false,
  total_deuda: 0,
  total_items: 0,
  origen: 'portal',
}

describe('claveSimit', () => {
  it('arma la llave con el tipo del API y solo dígitos del documento', () => {
    expect(claveSimit('CC', '1.023.454.321')).toBe('1:1023454321')
    expect(claveSimit('CE', '123456')).toBe('4:123456')
  })

  it('sin tipo o sin documento no hay consulta que disparar', () => {
    expect(claveSimit('', '1023454321')).toBe('')
    expect(claveSimit('CC', '')).toBe('')
    expect(claveSimit('CC', 'abc')).toBe('')
  })

  it('cambiar documento o tipo produce otra llave (re-dispara)', () => {
    const antes = claveSimit('CC', '1023454321')
    expect(claveSimit('CC', '1023454322')).not.toBe(antes)
    expect(claveSimit('CE', '1023454321')).not.toBe(antes)
    expect(claveSimit('CC', '1023454321')).toBe(antes)
  })
})

describe('documentoCompletoSimit', () => {
  it('la consulta automática espera el documento completo (6-10 dígitos)', () => {
    // Mientras digita, cada tecla sería otra consulta: solo se dispara
    // cuando el número ya es una cédula válida del formulario.
    expect(documentoCompletoSimit('12345')).toBe(false)
    expect(documentoCompletoSimit('123456')).toBe(true)
    expect(documentoCompletoSimit('1023454321')).toBe(true)
    expect(documentoCompletoSimit('1.023.454.321')).toBe(true)
    expect(documentoCompletoSimit('12345678901')).toBe(false)
    expect(documentoCompletoSimit('abc')).toBe(false)
    expect(documentoCompletoSimit('')).toBe(false)
  })
})

describe('interpretarSimit', () => {
  it('con deuda autocompleta Sí con monto e ítems', () => {
    const estado = interpretarSimit(conDeuda)
    expect(estado.tipo).toBe('con_deuda')
    expect(estado.tieneMultas).toBe(true)
    expect(estado.mensaje).toContain('$1.983.733')
    expect(estado.mensaje).toContain('2 registro(s)')
  })

  it('paz y salvo autocompleta No', () => {
    const estado = interpretarSimit(pazYSalvo)
    expect(estado.tipo).toBe('paz_y_salvo')
    expect(estado.tieneMultas).toBe(false)
    expect(estado.mensaje).toContain('paz y salvo')
  })

  it('deuda sin monto ni ítems igual autocompleta Sí', () => {
    const estado = interpretarSimit({ habilitado: true, tiene_multas: true })
    expect(estado.tipo).toBe('con_deuda')
    expect(estado.mensaje).toBe('SIMIT reporta deuda pendiente.')
  })

  it.each([
    [{ habilitado: false }, 'deshabilitado'],
    [{ habilitado: true }, 'proveedor sin respuesta'],
    [{ habilitado: true, tiene_multas: null }, 'tiene_multas null'],
  ] as const)('caída al manual: %s → %s', (res, caso) => {
    const estado = interpretarSimit(res)
    expect(estado.tipo, caso).toBe('manual')
    expect(estado.tieneMultas).toBeNull()
    expect(estado.mensaje).toBeNull()
  })
})
