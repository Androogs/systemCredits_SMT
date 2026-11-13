/**
 * Formas de pago de la originación (antes "líneas de crédito") — tabla
 * "Tasa de interés y fondo de garantía" (vigencia octubre 2026):
 *
 * - Crédito Directo (SUMOTO):  2,11 % m.v., de 1 a 48 meses.
 * - Sumoto Preferencial:       1,90 % m.v., de 1 a 48 meses.
 * - Credicontado: tasa 0 con cuota inicial y fondo de garantía por
 *   tramo de plazo (ver credicontado.ts).
 * - Contado: venta sin financiación — no lleva tasa comercial ni
 *   cuota; la evaluación corre con la operativa del motor.
 *
 * Las filas INVERSIONES de esa tabla corresponden al aliado anterior
 * y no aplican a estas líneas. Las líneas Sumoto no cobran cuota
 * inicial ni fondo de garantía.
 */
import { CREDICONTADO_TASA_MV } from './credicontado'

export const LINEA_CREDITO_DIRECTO = 'Crédito Directo'
export const LINEA_SUMOTO_PREFERENCIAL = 'Sumoto Preferencial'
export const LINEA_CREDICONTADO = 'Credicontado'
export const LINEA_CONTADO = 'Contado'

export const LINEAS_CREDITO = [
  LINEA_CREDITO_DIRECTO,
  LINEA_SUMOTO_PREFERENCIAL,
  LINEA_CREDICONTADO,
  LINEA_CONTADO,
] as const

/** Tasa comercial de cada línea en % m.v. */
export const TASA_LINEA_MV: Record<string, number> = {
  [LINEA_CREDITO_DIRECTO]: 2.11,
  [LINEA_SUMOTO_PREFERENCIAL]: 1.9,
  [LINEA_CREDICONTADO]: CREDICONTADO_TASA_MV,
}

/**
 * Tasa con la que se evalúa la línea: la comercial de la tabla topada
 * por la tasa operativa del producto (usura vigente − 1 pb), que es la
 * guarda `tasa < usura` del backend. Credicontado se evalúa con la
 * operativa del motor: su 0 % aplica solo al liquidar la oferta.
 * Contado no lleva tasa comercial: se evalúa con la operativa.
 * Líneas viejas o desconocidas conservan la operativa.
 */
export function tasaEvaluacionLinea(
  lineaCredito: string | null | undefined,
  tasaOperativa: number,
): number {
  if (
    !lineaCredito ||
    lineaCredito === LINEA_CREDICONTADO ||
    lineaCredito === LINEA_CONTADO
  ) {
    return tasaOperativa
  }
  const tasaTabla = TASA_LINEA_MV[lineaCredito]
  return tasaTabla == null ? tasaOperativa : Math.min(tasaTabla, tasaOperativa)
}
