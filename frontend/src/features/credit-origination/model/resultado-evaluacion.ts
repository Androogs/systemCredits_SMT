/**
 * Resultado de evaluación unificado: puede venir del motor real
 * (POST /api/solicitudes/{id}/evaluar) o del generador demo cuando el
 * backend no está disponible.
 */

import { valorPresenteAnualidad } from '../../../shared/lib/finanzas'
import type { ResultadoMotorApi } from '../api/originacionApi'

/** Alineada con `cupo_sugerido_tasa_pct` de parametros.json (motor). */
export const TASA_MENSUAL_REFERENCIA = 2
export const RATIO_CUOTA_INGRESO_MAX = 0.4
export const CUPO_MAXIMO = 20_000_000

export type DecisionCredito = 'APROBADO' | 'RECHAZADO' | 'REVISION_MANUAL'

export interface CausalEvaluacion {
  codigo: string
  descripcion: string
}

export interface ResultadoEvaluacionCredito {
  decision: DecisionCredito
  /** Decisión interna del motor (Estudio / Requiere Codeudor → perfil gris). */
  decisionInterna?: string
  /** Cupo máximo sugerido por el motor según la capacidad de pago. */
  montoSugerido: number
  /** Cuota mensual del cupo sugerido al plazo indicado. */
  cuotaSugerida: number
  plazoMeses: number
  tasaMensual: number
  causales: CausalEvaluacion[]
  advertencias: string[]
  scoreConsultado?: number
  /** Código del modelo de score consultado (p. ej. '67' HDC+). */
  scoreTipo?: string
  perfilScore?: string
  perfilIngreso?: string
  endeudamiento?: number
  capacidadPago?: number
  disponible?: number
  /** Ingreso final depurado por el motor y su fuente (valor_ingreso, quanto, declarado). */
  ingresoFinal?: number
  fuenteIngreso?: string
  ingresoFinalSmmlv?: number
  /** Bandeja completa de indicadores del buró calculada por el motor. */
  indicadoresBuro?: Record<string, unknown>
  trazabilidad: { etapa: string; resultado: string; detalle: string[] }[]
  evaluacionId?: string
  auditoria: string
  versionPolitica: string
  /** true cuando el resultado se generó localmente (sin backend). */
  esDemo: boolean
}

const num = (valor: string | number | null | undefined): number | undefined =>
  valor === null || valor === undefined ? undefined : Number(valor)

/**
 * Traduce la respuesta del motor al modelo del flujo. La decisión
 * pública es binaria; Estudio / Requiere Codeudor se presentan como
 * revisión manual (perfil gris) para el comité.
 */
export function resultadoDesdeApi(
  api: ResultadoMotorApi,
  plazoMeses: number,
): ResultadoEvaluacionCredito {
  const interna = api.decision_interna
  const decision: DecisionCredito =
    api.decision === 'Aprobado'
      ? 'APROBADO'
      : interna === 'Estudio' || interna === 'Requiere Codeudor'
        ? 'REVISION_MANUAL'
        : 'RECHAZADO'
  return {
    decision,
    decisionInterna: interna,
    montoSugerido: Number(api.cupo_sugerido),
    cuotaSugerida: Number(api.cuota_sugerida),
    plazoMeses,
    tasaMensual: TASA_MENSUAL_REFERENCIA,
    causales: api.causales.map((c) => ({
      codigo: c.codigo,
      descripcion: c.descripcion,
    })),
    advertencias: api.advertencias,
    scoreConsultado: num(api.score_consultado),
    scoreTipo: api.score_tipo ?? undefined,
    perfilScore: api.perfil_score ?? undefined,
    perfilIngreso: api.perfil_ingreso ?? undefined,
    endeudamiento: num(api.endeudamiento),
    capacidadPago: num(api.capacidad_pago),
    disponible: num(api.disponible),
    ingresoFinal: num(api.ingreso_final),
    fuenteIngreso: api.fuente_ingreso_final,
    ingresoFinalSmmlv: num(api.ingreso_final_smmlv),
    indicadoresBuro: api.indicadores_buro,
    trazabilidad: api.trazabilidad.map((p) => ({
      etapa: p.etapa,
      resultado: p.resultado,
      detalle: p.detalle,
    })),
    evaluacionId: api.evaluacion_id,
    auditoria: api.evaluacion_id,
    versionPolitica: 'PPT v4 / BRD',
    esDemo: false,
  }
}

/**
 * Cupo referencial local (misma fórmula que el motor): la cuota se
 * limita al menor entre el disponible declarado y el 40 % del ingreso,
 * y se trae a valor presente con la tasa de referencia.
 */
export function calcularCupoSugerido(
  ingresosMensuales: number,
  egresosMensuales: number,
  plazoMeses: number,
): { monto: number; cuota: number } {
  const disponible = Math.max(0, ingresosMensuales - egresosMensuales)
  const cuota = Math.round(
    Math.min(disponible, ingresosMensuales * RATIO_CUOTA_INGRESO_MAX),
  )
  const monto = Math.min(
    CUPO_MAXIMO,
    Math.round(
      valorPresenteAnualidad(cuota, TASA_MENSUAL_REFERENCIA, plazoMeses),
    ),
  )
  return { monto, cuota }
}

/** Resultado local cuando el backend no está disponible. */
export function crearResultadoDemo({
  decision,
  ingresosMensuales,
  egresosMensuales,
  plazoMeses,
}: {
  decision: DecisionCredito
  ingresosMensuales: number
  egresosMensuales: number
  plazoMeses: number
}): ResultadoEvaluacionCredito {
  const { monto, cuota } = calcularCupoSugerido(
    ingresosMensuales,
    egresosMensuales,
    plazoMeses,
  )
  return {
    decision,
    montoSugerido: monto,
    cuotaSugerida: cuota,
    plazoMeses,
    tasaMensual: TASA_MENSUAL_REFERENCIA,
    causales: [],
    advertencias: [],
    trazabilidad: [],
    auditoria: 'DEMO-LOCAL',
    versionPolitica: 'demo',
    esDemo: true,
  }
}
