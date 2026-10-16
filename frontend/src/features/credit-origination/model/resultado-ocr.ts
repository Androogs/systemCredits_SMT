/**
 * Resumen del OCR de la cédula que viaja en el contexto de la originación
 * (borrador local y pasos siguientes). Se construye a partir del resultado
 * fusionado anverso + reverso que entrega el backend (`ResultadoOCRApi`).
 */
export interface ResultadoOCR {
  numeroDocumento: string
  nombres: string
  apellidos: string
  fechaExpedicion: string
  /** false si la fecha de expiración (solo cédula blanca) ya pasó. */
  vigente: boolean
  /** 'rechazada' si el OCR no pudo leer la cédula: el asesor digita los datos. */
  calidadImagen: 'aprobada' | 'rechazada'
  /** true si anverso y reverso no concuerdan (posible documento alterado/ajeno). */
  alteraciones: boolean
  tipoCedula?: 'blanca' | 'amarilla' | null
  fechaNacimiento?: string
  fechaExpiracion?: string
}
