import { z } from 'zod'

export const financieroSchema = z.object({
  // null = campo vacío: se reporta como "ingresa los ingresos".
  ingresosMensuales: z
    .number()
    .positive('Ingresa los ingresos mensuales.')
    .nullable()
    .refine((v) => v != null, 'Ingresa los ingresos mensuales.'),
})
