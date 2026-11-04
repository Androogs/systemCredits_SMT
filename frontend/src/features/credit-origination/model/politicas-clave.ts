/**
 * Verificación de políticas clave (nacionalidad, tipo de documento y
 * multas): se capturan junto a los datos extraídos de la cédula.
 */

export interface DatosValidacion {
  tipoDocumento: string
  numeroDocumento: string
  /** ISO 'YYYY-MM-DD': la lee el OCR y la confirma el asesor. */
  fechaNacimiento: string
  nacionalidad: string
  multasPendientes: boolean
}

export const NACIONALIDADES = [
  'Colombiano(a)',
  'Venezolano(a)',
  'Otra',
] as const
export type Nacionalidad = (typeof NACIONALIDADES)[number]

// Al backend va el país canónico, no la etiqueta del select: el motor
// compara el texto literal para la política R21 (nacionalidad colombiana).
export const NACIONALIDAD_API: Record<Nacionalidad, string> = {
  'Colombiano(a)': 'Colombia',
  'Venezolano(a)': 'Venezuela',
  Otra: 'Otra',
}

/** Etiqueta del select a partir del país canónico guardado. */
export function nacionalidadDesdeApi(valor?: string): Nacionalidad | '' {
  return NACIONALIDADES.find((n) => NACIONALIDAD_API[n] === valor) ?? ''
}

export interface DocumentoOpcion {
  codigo: string
  nombre: string
  /** Insignia corta junto al número de documento. */
  insignia: string
}

// El tipo de documento depende de la nacionalidad: a un colombiano se le
// exige CC; al extranjero, su cédula de extranjería (PPT/pasaporte aún no
// habilitados para crédito).
export const DOCUMENTOS_POR_NACIONALIDAD: Record<
  Nacionalidad,
  DocumentoOpcion[]
> = {
  'Colombiano(a)': [
    { codigo: 'CC', nombre: 'Cédula de Ciudadanía', insignia: 'CC COLOMBIANA' },
  ],
  'Venezolano(a)': [
    { codigo: 'CE', nombre: 'Cédula de Extranjería', insignia: 'CE' },
  ],
  Otra: [{ codigo: 'CE', nombre: 'Cédula de Extranjería', insignia: 'CE' }],
}
