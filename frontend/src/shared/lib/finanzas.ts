/**
 * Funciones financieras del simulador y del formulario de solicitud.
 * Espejan backend/services/finanzas.py (anualidad francesa).
 */

export function cuotaAnualidad(
  monto: number,
  tasaPct: number,
  plazoMeses: number,
): number {
  if (plazoMeses <= 0) return 0
  const i = tasaPct / 100
  if (i === 0) return monto / plazoMeses
  return (monto * i) / (1 - Math.pow(1 + i, -plazoMeses))
}

export function valorPresenteAnualidad(
  cuota: number,
  tasaPct: number,
  plazoMeses: number,
): number {
  if (plazoMeses <= 0) return 0
  const i = tasaPct / 100
  if (i === 0) return cuota * plazoMeses
  return (cuota * (1 - Math.pow(1 + i, -plazoMeses))) / i
}

/**
 * Usura operativa en m.v. a partir de la usura de consumo y ordinario
 * en E.A. publicada por la SFC: se convierte a mensual y se trunca a 4
 * decimales con floor para quedar siempre un pelo por debajo del límite
 * legal (la conversión de 28,59% EA da 2,11760008…% → 2,1176%).
 */
export function usuraOperativaMv(
  usuraEa: number | null | undefined,
): number | null {
  if (!usuraEa) return null
  const mv = ((1 + usuraEa / 100) ** (1 / 12) - 1) * 100
  return Math.floor(mv * 1e4) / 1e4
}

/** Holgura bajo la usura: la guarda de cumplimiento del backend rechaza
 *  cualquier tasa que iguale la usura ya redondeada a 4 decimales, así
 *  que la tasa del producto queda un punto base por debajo. */
const MARGEN_BAJO_USURA_MV = 0.0001

/**
 * Tasa del producto en m.v.: la usura operativa menos la holgura — la
 * máxima tasa legalmente cobrable que pasa la validación `tasa < usura`.
 */
export function tasaProductoMv(
  usuraEa: number | null | undefined,
): number | null {
  const usura = usuraOperativaMv(usuraEa)
  if (usura == null) return null
  return Math.round((usura - MARGEN_BAJO_USURA_MV) * 1e4) / 1e4
}

export interface FilaAmortizacion {
  mes: number
  cuota: number
  interes: number
  abonoCapital: number
  saldo: number
}

export function tablaAmortizacion(
  monto: number,
  tasaPct: number,
  plazoMeses: number,
): FilaAmortizacion[] {
  const cuota = cuotaAnualidad(monto, tasaPct, plazoMeses)
  const i = tasaPct / 100
  const filas: FilaAmortizacion[] = []
  let saldo = monto
  for (let mes = 1; mes <= plazoMeses; mes += 1) {
    const interes = saldo * i
    const abonoCapital = cuota - interes
    saldo = Math.max(0, saldo - abonoCapital)
    filas.push({ mes, cuota, interes, abonoCapital, saldo })
  }
  return filas
}
