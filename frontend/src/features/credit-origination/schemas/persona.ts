import { z } from 'zod'

export const EDAD_MINIMA = 18
// El motor (R13) rechaza edad >= edad_maxima_be (=66), así que el
// máximo permitido para radicar es 65 inclusive.
export const EDAD_MAXIMA = 65

/** Número de documento tal como lo digita el asesor: solo dígitos. */
export const numeroDocumentoSchema = z
  .string()
  .regex(
    /^\d{6,10}$/,
    'Ingresa un número de cédula válido, entre 6 y 10 dígitos.',
  )

/** Número de identificación que viene del OCR, con puntos de miles. */
export const numeroIdentificacionSchema = z.preprocess(
  (valor) => (typeof valor === 'string' ? valor.replace(/\D/g, '') : valor),
  numeroDocumentoSchema,
)

export const validacionInicialSchema = z.object({
  numeroDocumento: numeroDocumentoSchema,
  edad: z.preprocess(
    (valor) => {
      if (typeof valor === 'string' && valor.trim() === '') return NaN
      return typeof valor === 'string' ? Number(valor) : valor
    },
    z
      .number({ invalid_type_error: 'Ingresa la edad del solicitante.' })
      .int(`La edad debe estar entre ${EDAD_MINIMA} y ${EDAD_MAXIMA} años.`)
      .min(
        EDAD_MINIMA,
        `La edad debe estar entre ${EDAD_MINIMA} y ${EDAD_MAXIMA} años.`,
      )
      .max(
        EDAD_MAXIMA,
        `La edad debe estar entre ${EDAD_MINIMA} y ${EDAD_MAXIMA} años.`,
      ),
  ),
  multas: z.enum(['si', 'no'], {
    errorMap: () => ({ message: 'Selecciona una opción para continuar.' }),
  }),
})

export const datosPersonalesSchema = z
  .object({
    nombres: z.string().trim().min(1, 'Los nombres son obligatorios.'),
    apellidos: z.string().trim().min(1, 'Los apellidos son obligatorios.'),
    numeroIdentificacion: numeroIdentificacionSchema,
    sexo: z.string().min(1, 'Selecciona el sexo.'),
    fechaNacimiento: z
      .string()
      .min(1, 'Ingresa la fecha de nacimiento.')
      .refine((fecha) => {
        const nacimiento = new Date(fecha)
        const hoy = new Date()
        let edad = hoy.getFullYear() - nacimiento.getFullYear()
        const mes = hoy.getMonth() - nacimiento.getMonth()
        if (mes < 0 || (mes === 0 && hoy.getDate() < nacimiento.getDate()))
          edad -= 1
        return edad >= EDAD_MINIMA && edad <= EDAD_MAXIMA
      }, `La fecha de nacimiento debe corresponder a una edad entre ${EDAD_MINIMA} y ${EDAD_MAXIMA} años.`),
    lugarNacimiento: z
      .string()
      .trim()
      .min(1, 'Confirma el lugar de nacimiento.'),
    fechaExpedicion: z.string().min(1, 'Ingresa la fecha de expedición.'),
    ciudadExpedicion: z
      .string()
      .trim()
      .min(1, 'Confirma la ciudad de expedición.'),
  })
  .superRefine((datos, ctx) => {
    if (
      datos.fechaNacimiento &&
      datos.fechaExpedicion &&
      datos.fechaExpedicion <= datos.fechaNacimiento
    ) {
      ctx.addIssue({
        code: 'custom',
        path: ['fechaExpedicion'],
        message:
          'La fecha de expedición debe ser posterior a la fecha de nacimiento.',
      })
    }
  })
