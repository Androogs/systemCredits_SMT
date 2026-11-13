// Parámetros de la línea Credicontado (vigencia oct-2026): sin interés
// (tasa N/A en la tabla comercial); la cuota inicial y el fondo de
// garantía son fijos por rango de plazo — la política los impone y el
// asesor no puede modificarlos.
export const CREDICONTADO_PLAZO_MIN = 1
export const CREDICONTADO_PLAZO_MAX = 12
export const CREDICONTADO_TASA_MV = 0

// Plazos que la línea ofrece comercialmente: la tabla de comparación
// del simulador solo presenta estas opciones.
export const CREDICONTADO_PLAZOS_TABLA = [4, 6, 8, 12]

export const CREDICONTADO_TRAMOS = [
  { hasta: 3, cuotaInicial: 0.4, fondo: 0.02 },
  { hasta: 6, cuotaInicial: 0.4, fondo: 0.06 },
  { hasta: 11, cuotaInicial: 0.6, fondo: 0.08 },
  { hasta: 12, cuotaInicial: 0.7, fondo: 0.1 },
] as const

/** Tramo vigente para un plazo dado; fuera de tabla aplica el último. */
export function tramoCredicontado(plazoMeses: number) {
  return (
    CREDICONTADO_TRAMOS.find((t) => plazoMeses <= t.hasta) ??
    CREDICONTADO_TRAMOS[CREDICONTADO_TRAMOS.length - 1]
  )
}

/** Acota un plazo al rango que financia Credicontado (1–12 meses). */
export function plazoCredicontado(plazoMeses: number) {
  return Math.min(
    CREDICONTADO_PLAZO_MAX,
    Math.max(CREDICONTADO_PLAZO_MIN, plazoMeses),
  )
}
