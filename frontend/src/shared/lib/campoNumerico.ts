/**
 * Utilidades de `CampoNumerico`: texto crudo editable, coma o punto
 * decimal, sin ceros a la izquierda pegados al reescribir.
 */

/** Enteros: solo dígitos y sin ceros iniciales ("01000000" → "1000000"). */
export function limpiarEntero(texto: string): string {
  return texto.replace(/\D/g, '').replace(/^0+(?=\d)/, '')
}

/**
 * Decimales: acepta coma o punto; solo el primer separador cuenta
 * ("12.34.56" → "12.3456").
 */
export function limpiarDecimal(texto: string): string {
  const normalizado = texto.replace(',', '.').replace(/[^\d.]/g, '')
  const partes = normalizado.split('.')
  const unico =
    partes.length > 2 ? `${partes[0]}.${partes.slice(1).join('')}` : normalizado
  return unico.replace(/^0+(?=\d)/, '')
}

/**
 * Decimales en modo miles: '.' es separador de miles (se descarta) y
 * ',' el separador decimal es-CO. Devuelve el texto limpio con '.'
 * interno para `parsearNumerico` ("1.234,5" → "1234.5").
 */
export function limpiarDecimalMiles(texto: string): string {
  const partes = texto.replace(/\./g, '').replace(',', '.').split('.')
  const entero = limpiarEntero(partes[0])
  if (partes.length === 1) return entero
  const decimal = partes.slice(1).join('').replace(/\D/g, '')
  return `${entero}.${decimal}`
}

/** "1234567" → "1.234.567"; con decimal interno "1234.5" → "1.234,5". */
export function formatearMiles(texto: string): string {
  const [entero, ...resto] = texto.split('.')
  const enteroFmt = entero.replace(/\B(?=(\d{3})+(?!\d))/g, '.')
  return resto.length === 0 ? enteroFmt : `${enteroFmt},${resto.join('')}`
}

/** Índice tras `n` dígitos (ignora separadores); 0 → 0; sin suficientes → largo. */
export function posicionTrasDigitos(texto: string, n: number): number {
  if (n <= 0) return 0
  let vistos = 0
  for (let i = 0; i < texto.length; i++) {
    const c = texto.charCodeAt(i)
    if (c >= 48 && c <= 57 && ++vistos === n) return i + 1
  }
  return texto.length
}

/** Texto → número; cadena vacía o "." intermedio → null. */
export function parsearNumerico(texto: string): number | null {
  if (texto === '' || texto === '.') return null
  const numero = Number(texto)
  return Number.isFinite(numero) ? numero : null
}

/** Acota un valor al rango [minimo, maximo]. */
export function acotar(
  valor: number,
  minimo?: number,
  maximo?: number,
): number {
  return Math.min(
    maximo ?? Number.POSITIVE_INFINITY,
    Math.max(minimo ?? Number.NEGATIVE_INFINITY, valor),
  )
}
