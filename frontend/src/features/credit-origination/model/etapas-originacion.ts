export const etapasOriginacion = [
  { titulo: 'Validación Inicial', detalle: 'Datos básicos y filtros' },
  { titulo: 'Tratamiento de Datos', detalle: 'Consentimiento informado' },
  { titulo: 'Captura de Cédula', detalle: 'Anverso y reverso' },
  { titulo: 'Procesamiento OCR', detalle: 'Extracción y biometría' },
  { titulo: 'Verificación de Datos', detalle: 'Confirmación de campos' },
  { titulo: 'Resultado Validación', detalle: 'Resumen y radicación' },
  { titulo: 'Creación de Solicitud', detalle: 'Datos financieros' },
  { titulo: 'Preparación de Consulta', detalle: 'Autorización de buró' },
  { titulo: 'Consulta en Curso', detalle: 'Datacrédito API' },
  { titulo: 'Informe Crediticio', detalle: 'Análisis de score' },
  { titulo: 'Evaluación Integral', detalle: 'Motor de políticas' },
  { titulo: 'Resultado Final', detalle: 'Firma y desembolso' },
] as const

export type PasoOriginacion = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12
