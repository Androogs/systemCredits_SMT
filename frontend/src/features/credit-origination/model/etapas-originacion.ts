export const etapasOriginacion = [
  { titulo: 'Validación Inicial', detalle: 'Documento y filtros' },
  { titulo: 'Autorización', detalle: 'Habeas Data' },
  { titulo: 'Evidencia y Datos', detalle: 'Cédula, video y OCR' },
  { titulo: 'Perfil Económico', detalle: 'Ingresos y capacidad' },
  { titulo: 'Decisión y Moto', detalle: 'Decisión del motor' },
] as const

export type PasoOriginacion = 1 | 2 | 3 | 4 | 5
