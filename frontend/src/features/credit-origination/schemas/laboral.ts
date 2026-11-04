import { z, type RefinementCtx } from 'zod'

export const OCUPACIONES = [
  'Empleado',
  'Independiente',
  'Pensionado',
  'Fuerzas Militares',
] as const

/** Tipos de contrato válidos cuando la ocupación es Empleado. */
export const TIPOS_CONTRATO = ['Indefinido', 'Fijo', 'Obra o Labor'] as const

export const SUBTIPOS_INDEPENDIENTE = [
  'Profesional independiente',
  'Comerciante independiente',
] as const

export const ENTIDADES_PENSION = [
  'Colpensiones',
  'Protección',
  'Porvenir',
  'Colfondos',
  'Skandia',
  'Old Mutual',
  'Horizonte',
  'Otra',
] as const

export const INSTITUCIONES_FUERZAS = [
  'Ejército Nacional',
  'Armada Nacional',
  'Fuerza Aérea Colombiana',
  'Policía Nacional',
  'INPEC',
  'Otra',
] as const

export const laboralSchemaBase = z.object({
  ocupacion: z
    .string()
    .min(1, 'Selecciona la ocupación principal.')
    .refine(
      (valor) => OCUPACIONES.includes(valor as (typeof OCUPACIONES)[number]),
      'Selecciona la ocupación principal.',
    ),
  /** Solo aplica (y es obligatorio) para Empleado; vacío en el resto. */
  tipoContrato: z.string(),
  /** Solo para Independiente. */
  subtipoIndependiente: z.string(),
  empresa: z.string().trim(),
  /** Solo para Empleado. En Pensionado / Fuerzas / Independiente no aplica. */
  mesesContinuidad: z
    .number()
    .min(0, 'La continuidad no puede ser negativa.')
    .nullable(),
  aniosCamara: z
    .number({ invalid_type_error: 'Ingresa un número válido.' })
    .nullable(),
  /** Fondo de pensiones / entidad pagadora / fuerza. */
  entidadPagadora: z.string(),
})

/**
 * Reglas condicionales por ocupación:
 * - Empleado: tipo de contrato y meses de continuidad obligatorios.
 * - Independiente: subtipo y años de Cámara de Comercio obligatorios.
 * - Pensionado / Fuerzas: entidad pagadora / institución obligatoria.
 */
export const refinarLaboral = (
  datos: {
    ocupacion: string
    tipoContrato: string
    subtipoIndependiente: string
    mesesContinuidad: number | null
    aniosCamara: number | null
    entidadPagadora: string
    empresa: string
  },
  ctx: RefinementCtx,
) => {
  if (
    datos.ocupacion !== 'Pensionado' &&
    datos.ocupacion !== 'Fuerzas Militares' &&
    !datos.empresa.trim()
  ) {
    ctx.addIssue({
      code: 'custom',
      path: ['empresa'],
      message:
        datos.ocupacion === 'Independiente'
          ? 'Ingresa el negocio o actividad.'
          : 'Ingresa la empresa o empleador.',
    })
  }

  if (
    datos.ocupacion === 'Empleado' &&
    !TIPOS_CONTRATO.includes(
      datos.tipoContrato as (typeof TIPOS_CONTRATO)[number],
    )
  ) {
    ctx.addIssue({
      code: 'custom',
      path: ['tipoContrato'],
      message: 'Selecciona el tipo de contrato del empleado.',
    })
  }
  if (
    datos.ocupacion === 'Empleado' &&
    (datos.mesesContinuidad == null || datos.mesesContinuidad <= 0)
  ) {
    ctx.addIssue({
      code: 'custom',
      path: ['mesesContinuidad'],
      message: 'Ingresa los meses de continuidad laboral.',
    })
  }
  if (
    datos.ocupacion === 'Independiente' &&
    !SUBTIPOS_INDEPENDIENTE.includes(
      datos.subtipoIndependiente as (typeof SUBTIPOS_INDEPENDIENTE)[number],
    )
  ) {
    ctx.addIssue({
      code: 'custom',
      path: ['subtipoIndependiente'],
      message: 'Selecciona el tipo de independiente.',
    })
  }
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
  if (
    (datos.ocupacion === 'Pensionado' ||
      datos.ocupacion === 'Fuerzas Militares') &&
    !datos.entidadPagadora.trim()
  ) {
    ctx.addIssue({
      code: 'custom',
      path: ['entidadPagadora'],
      message: 'Selecciona la entidad pagadora o institución.',
    })
  }
}

export const laboralSchema = laboralSchemaBase.superRefine(refinarLaboral)
