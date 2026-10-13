export interface ResultadoOCR {
  numeroDocumento: string
  nombres: string
  apellidos: string
  fechaExpedicion: string
  vigente: boolean
  calidadImagen: 'aprobada' | 'rechazada'
  alteraciones: boolean
}
