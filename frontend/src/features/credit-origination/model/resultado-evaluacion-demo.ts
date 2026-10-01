export type DecisionCreditoDemo = 'APROBADO' | 'REVISION_MANUAL'

export interface ResultadoEvaluacionCreditoDemo {
  decision: DecisionCreditoDemo
  montoSolicitado: number
  montoMaximoSugerido: number
  montoAprobado: number
  desembolsoEstimado: number
  plazoMeses: number
  cuotaMensual: number
  tasaMensual: number
  auditoria: string
  versionPolitica: string
}

interface ParametrosEvaluacionCreditoDemo {
  decision: DecisionCreditoDemo
  montoSolicitado: number
  plazoMeses: number
}

const MONTO_MAXIMO_SUGERIDO = 18_500_000
const MONTO_BASE_DEMO = 15_000_000
const CUOTA_BASE_DEMO = 540_000
const TASA_MENSUAL_DEMO = 1.85

export function crearResultadoEvaluacionCreditoDemo({
  decision,
  montoSolicitado,
  plazoMeses,
}: ParametrosEvaluacionCreditoDemo): ResultadoEvaluacionCreditoDemo {
  const montoAprobado =
    decision === 'APROBADO'
      ? Math.min(montoSolicitado, MONTO_MAXIMO_SUGERIDO)
      : 0

  return {
    decision,
    montoSolicitado,
    montoMaximoSugerido: MONTO_MAXIMO_SUGERIDO,
    montoAprobado,
    desembolsoEstimado: Math.round(montoAprobado * 0.99),
    plazoMeses,
    cuotaMensual: Math.round(
      (montoAprobado / MONTO_BASE_DEMO) * CUOTA_BASE_DEMO,
    ),
    tasaMensual: TASA_MENSUAL_DEMO,
    auditoria: 'RULE-EVAL-4481',
    versionPolitica: 'v2026.1',
  }
}
