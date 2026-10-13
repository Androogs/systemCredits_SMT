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
