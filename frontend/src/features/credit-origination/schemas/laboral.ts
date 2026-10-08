import { z, type RefinementCtx } from 'zod'

export const OCUPACIONES = [
  'Empleado Término Indefinido',
  'Empleado Término Fijo',
  'Independiente',
  'Pensionado',
  'Prestador de Servicios',
] as const

export const laboralSchemaBase = z.object({
  ocupacion: z
    .string()
    .min(1, 'Selecciona la ocupación principal.')
    .refine(
      (valor) => OCUPACIONES.includes(valor as (typeof OCUPACIONES)[number]),
      'Selecciona la ocupación principal.',
    ),
  empresa: z.string().trim().min(1, 'Ingresa la empresa o empleador.'),
  mesesContinuidad: z.number().min(0, 'La continuidad no puede ser negativa.'),
  aniosCamara: z
    .number({ invalid_type_error: 'Ingresa un número válido.' })
    .nullable(),
})

/**
 * R16: la Cámara de Comercio es obligatoria (y > 0) para independientes;
 * en las demás ocupaciones es opcional pero nunca negativa.
 */
export const refinarLaboral = (
  datos: { ocupacion: string; aniosCamara: number | null },
  ctx: RefinementCtx,
) => {
  if (
    datos.ocupacion === 'Independiente' &&
    (datos.aniosCamara === null || datos.aniosCamara <= 0)
  ) {
    ctx.addIssue({
      code: 'custom',
      path: ['aniosCamara'],
      message:
        'Requerido para independientes: el motor rechaza sin Cámara de Comercio (R16).',
    })
  } else if (datos.aniosCamara !== null && datos.aniosCamara < 0) {
    ctx.addIssue({
      code: 'custom',
      path: ['aniosCamara'],
      message: 'Los años de Cámara no pueden ser negativos.',
    })
  }
}

export const laboralSchema = laboralSchemaBase.superRefine(refinarLaboral)
