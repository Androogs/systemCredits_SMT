import { z } from 'zod'

export const financieroSchema = z.object({
  ingresosMensuales: z.number().positive('Ingresa los ingresos mensuales.'),
  egresosMensuales: z.number().min(0, 'Los egresos no pueden ser negativos.'),
})
