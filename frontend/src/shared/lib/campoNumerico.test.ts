import { describe, expect, it } from 'vitest'
import {
  acotar,
  formatearMiles,
  limpiarDecimal,
  limpiarDecimalMiles,
  limpiarEntero,
  parsearNumerico,
  posicionTrasDigitos,
} from './campoNumerico'

describe('limpiarEntero', () => {
  it('quita caracteres no numéricos', () => {
    expect(limpiarEntero('$10.000.000')).toBe('10000000')
    expect(limpiarEntero('abc')).toBe('')
  })

  it('permite dejar el campo vacío', () => {
    expect(limpiarEntero('')).toBe('')
  })

  it('quita el cero pegado al reescribir (01000000 → 1000000)', () => {
    expect(limpiarEntero('01000000')).toBe('1000000')
    expect(limpiarEntero('01')).toBe('1')
    expect(limpiarEntero('00')).toBe('0')
  })

  it('conserva un único cero', () => {
    expect(limpiarEntero('0')).toBe('0')
  })
})

describe('limpiarDecimal', () => {
  it('normaliza la coma decimal a punto', () => {
    expect(limpiarDecimal('1,5')).toBe('1.5')
    expect(limpiarDecimal('2,3')).toBe('2.3')
  })

  it('conserva el estado intermedio "3." para seguir digitando', () => {
    expect(limpiarDecimal('3.')).toBe('3.')
    expect(limpiarDecimal('3,')).toBe('3.')
  })

  it('ignora separadores extra después del primero', () => {
    expect(limpiarDecimal('1.5.2')).toBe('1.52')
  })

  it('conserva decimales que empiezan en cero', () => {
    expect(limpiarDecimal('0.5')).toBe('0.5')
    expect(limpiarDecimal('0,5')).toBe('0.5')
  })

  it('quita ceros a la izquierda de la parte entera', () => {
    expect(limpiarDecimal('01.5')).toBe('1.5')
    expect(limpiarDecimal('00.5')).toBe('0.5')
  })

  it('rechaza letras y símbolos', () => {
    expect(limpiarDecimal('abc')).toBe('')
    expect(limpiarDecimal('1e5')).toBe('15')
    expect(limpiarDecimal('-3')).toBe('3')
  })
})

describe('formatearMiles', () => {
  it('agrupa de a tres con punto es-CO mientras se digita', () => {
    expect(formatearMiles('1')).toBe('1')
    expect(formatearMiles('1234')).toBe('1.234')
    expect(formatearMiles('1234567')).toBe('1.234.567')
    expect(formatearMiles('12781665')).toBe('12.781.665')
  })

  it('vacío queda vacío', () => {
    expect(formatearMiles('')).toBe('')
  })

  it('con decimal interno usa coma es-CO', () => {
    expect(formatearMiles('1234.5')).toBe('1.234,5')
    expect(formatearMiles('1234567.')).toBe('1.234.567,')
  })
})

describe('limpiarDecimalMiles', () => {
  it('el punto es separador de miles y la coma el decimal', () => {
    expect(limpiarDecimalMiles('1.234,5')).toBe('1234.5')
    expect(limpiarDecimalMiles('12.345.678')).toBe('12345678')
  })

  it('sin coma devuelve solo la parte entera', () => {
    expect(limpiarDecimalMiles('1.234')).toBe('1234')
  })

  it('conserva coma intermedia para seguir digitando', () => {
    expect(limpiarDecimalMiles('1.234,')).toBe('1234.')
  })
})

describe('posicionTrasDigitos', () => {
  it('encuentra el índice tras n dígitos ignorando separadores', () => {
    expect(posicionTrasDigitos('1.234.567', 4)).toBe(5)
    expect(posicionTrasDigitos('1.234.567', 1)).toBe(1)
    expect(posicionTrasDigitos('1.234.567', 7)).toBe(9)
  })

  it('cero dígitos → inicio; más dígitos que los que hay → final', () => {
    expect(posicionTrasDigitos('1.234', 0)).toBe(0)
    expect(posicionTrasDigitos('1.234', 99)).toBe(5)
  })
})

describe('parsearNumerico', () => {
  it('vacío y "." intermedio devuelven null (sin Number("") = 0)', () => {
    expect(parsearNumerico('')).toBeNull()
    expect(parsearNumerico('.')).toBeNull()
  })

  it('convierte decimales y enteros', () => {
    expect(parsearNumerico('3.5')).toBe(3.5)
    expect(parsearNumerico('3.')).toBe(3)
    expect(parsearNumerico('4500000')).toBe(4_500_000)
  })
})

describe('acotar', () => {
  it('respeta mínimo y máximo al salir del campo', () => {
    expect(acotar(-5, 0, 100)).toBe(0)
    expect(acotar(150, 0, 100)).toBe(100)
    expect(acotar(50, 0, 100)).toBe(50)
  })

  it('sin límites devuelve el valor', () => {
    expect(acotar(999)).toBe(999)
  })
})
