/**
 * Validación en tiempo real del formulario de solicitud (paso 7) con Zod.
 * Las reglas replican la política de captura: campos obligatorios,
 * no-negativos y la regla condicional de Cámara de Comercio para
 * independientes (el motor rechaza sin ella — causal R16).
 *
 * Compone los schemas dedicados por dominio:
 * - schemas/laboral.ts    → ocupación, empresa, continuidad, Cámara
 * - schemas/financiero.ts → ingresos y egresos mensuales
 * (schemas/persona.ts cubre los pasos 1 y 5 del wizard).
 */

import { z } from 'zod'
import { laboralSchemaBase, refinarLaboral } from '../schemas/laboral'
import { financieroSchema } from '../schemas/financiero'
import type { DatosSolicitud } from '../ui/CrearSolicitud'

export const solicitudSchema = z
  .object({
    lineaCredito: z.string().min(1, 'Selecciona la línea de crédito.'),
    destinoCredito: z.string().min(1, 'Selecciona el destino del crédito.'),
    plazoMeses: z
      .number()
      .int('El plazo debe ser un número entero de meses.')
      .min(12, 'El plazo debe estar entre 12 y 48 meses.')
      .max(48, 'El plazo debe estar entre 12 y 48 meses.'),
  })
  .merge(laboralSchemaBase)
  .merge(financieroSchema)
  .superRefine(refinarLaboral)

export type ErroresSolicitud = Partial<Record<keyof DatosSolicitud, string>>

/** Primer mensaje de error por campo, listo para pintar bajo el input. */
export function erroresSolicitud(datos: DatosSolicitud): ErroresSolicitud {
  const resultado = solicitudSchema.safeParse(datos)
  if (resultado.success) return {}
  const errores: ErroresSolicitud = {}
  for (const issue of resultado.error.issues) {
    const campo = issue.path[0] as keyof DatosSolicitud
    if (campo && !(campo in errores)) errores[campo] = issue.message
  }
  return errores
}
