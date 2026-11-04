export const etapasOriginacion = [
  { titulo: 'Autorización', detalle: 'Habeas Data' },
  { titulo: 'Evidencia', detalle: 'Cédula y video' },
  { titulo: 'Datos y Políticas', detalle: 'OCR y filtros clave' },
  { titulo: 'Perfil Económico', detalle: 'Ingresos y capacidad' },
  { titulo: 'Decisión y Moto', detalle: 'Decisión del motor' },
] as const

export type PasoOriginacion = 1 | 2 | 3 | 4 | 5
