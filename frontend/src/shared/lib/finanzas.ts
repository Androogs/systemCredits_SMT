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
