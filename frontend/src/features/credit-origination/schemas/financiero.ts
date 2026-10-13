import { z } from 'zod'

export const financieroSchema = z.object({
  ingresosMensuales: z.number().positive('Ingresa los ingresos mensuales.'),
})
