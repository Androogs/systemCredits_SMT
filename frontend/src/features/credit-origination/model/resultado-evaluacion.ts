/**
 * Resultado de evaluación unificado: puede venir del motor real
 * (POST /api/solicitudes/{id}/evaluar) o del generador demo cuando el
 * backend no está disponible.
 */

import {
  cuotaAnualidad,
  valorPresenteAnualidad,
} from '../../../shared/lib/finanzas'
import type { ResultadoEvaluacionApi } from '../api/originacionApi'
import { esResultadoInterno } from '../api/originacionApi'

/**
 * Tasa comercial del producto y referencia del motor: la usura de
 * consumo y ordinario vigente (28,59% EA → 2,1176% m.v.) menos un punto
 * base (`tasaProductoMv`): la máxima cobrable que pasa la guarda
 * `tasa < usura` del backend. Alineada con `cupo_sugerido_tasa_pct` de
 * parametros.json (motor). Cuando la consulta SFC responde, la
 * evaluación se corre con la usura vigente en vivo; esta constante es
 * el respaldo.
 */
export const TASA_MENSUAL_REFERENCIA = 2.1175
/**
 * Prima del seguro de vida deudores incluida en la cuota: % mensual
 * sobre el saldo financiado. Espeja `seguro_producto.tasa_prima`
 * del catálogo (prima vigente del negocio: 0,35 %).
 */
export const PRIMA_SEGURO_VIDA_PCT = 0.35
/** Gastos administrativos de originación: cargo fijo que se financia
 *  dentro del saldo. Espeja `GASTOS_ADMINISTRATIVOS` del backend
 *  (desembolso_service) — queda descompuesto en el crédito. */
export const GASTOS_ADMINISTRATIVOS = 200_000
export const RATIO_CUOTA_INGRESO_MAX = 0.4
export const CUPO_MAXIMO = 20_000_000

/** Parámetros replicados del motor para el cálculo estimado en frontend. */
export const SMMLV = 1_750_905
export const GASTOS_PERSONALES_PCT_BAJO = 0.5
export const GASTOS_PERSONALES_PCT_MEDIO = 0.45
export const GASTOS_PERSONALES_PCT_ALTO = 0.4
export const GASTOS_PERSONALES_UMBRAL_MEDIO = 1.6
export const GASTOS_PERSONALES_UMBRAL_ALTO = 2.0
export const CAPACIDAD_PAGO_PCT = 0.7
export const CUPO_PLAZO_MESES = 24

/** Decisión visible del flujo: binaria (sin estudio ni comité). */
export type DecisionCredito = 'APROBADO' | 'RECHAZADO'

export interface CausalEvaluacion {
  codigo: string
  descripcion: string
}

export interface ResultadoEvaluacionCredito {
  decision: DecisionCredito
  /** Decisión interna del motor: también binaria (D185); 'Estudio' y
   * 'Requiere Codeudor' solo aparecen en evaluaciones históricas. */
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
  /** Ingreso final depurado por el motor y su fuente (valor_ingreso o quanto; el declarado no es fuente). */
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
 * Traduce la respuesta del motor al modelo del flujo. La decisión es
 * estrictamente binaria — interna y pública (D185); 'Estudio' y
 * 'Requiere Codeudor' solo llegan en evaluaciones históricas.
 *
 * Acepta la respuesta interna (admin) o la binaria (asesor/aliado): en
 * esta última el backend omite score, causales e indicadores de buró.
 */
export function resultadoDesdeApi(
  api: ResultadoEvaluacionApi,
  plazoMeses: number,
): ResultadoEvaluacionCredito {
  const interno = esResultadoInterno(api)
  const decision: DecisionCredito =
    api.decision === 'Aprobado' ? 'APROBADO' : 'RECHAZADO'
  return {
    decision,
    decisionInterna: interno ? api.decision_interna : undefined,
    montoSugerido: Number(api.cupo_sugerido),
    cuotaSugerida: Number(api.cuota_sugerida),
    plazoMeses,
    tasaMensual: TASA_MENSUAL_REFERENCIA,
    causales: interno
      ? api.causales.map((c) => ({
          codigo: c.codigo,
          descripcion: c.descripcion,
        }))
      : [],
    advertencias: api.advertencias,
    scoreConsultado: interno ? num(api.score_consultado) : undefined,
    scoreTipo: interno ? (api.score_tipo ?? undefined) : undefined,
    perfilScore: interno ? (api.perfil_score ?? undefined) : undefined,
    perfilIngreso: interno ? (api.perfil_ingreso ?? undefined) : undefined,
    endeudamiento: interno ? num(api.endeudamiento) : undefined,
    capacidadPago: interno ? num(api.capacidad_pago) : undefined,
    disponible: interno ? num(api.disponible) : undefined,
    ingresoFinal: interno ? num(api.ingreso_final) : undefined,
    fuenteIngreso: interno ? api.fuente_ingreso_final : undefined,
    ingresoFinalSmmlv: interno ? num(api.ingreso_final_smmlv) : undefined,
    indicadoresBuro: interno ? api.indicadores_buro : undefined,
    trazabilidad: interno
      ? api.trazabilidad.map((p) => ({
          etapa: p.etapa,
          resultado: p.resultado,
          detalle: p.detalle,
        }))
      : [],
    evaluacionId: api.evaluacion_id,
    auditoria: api.evaluacion_id,
    versionPolitica: 'PPT v4 / BRD',
    esDemo: false,
  }
}

function gastosPersonalesPct(ingresoSmmlv: number): number {
  if (ingresoSmmlv < GASTOS_PERSONALES_UMBRAL_MEDIO)
    return GASTOS_PERSONALES_PCT_BAJO
  if (ingresoSmmlv < GASTOS_PERSONALES_UMBRAL_ALTO)
    return GASTOS_PERSONALES_PCT_MEDIO
  return GASTOS_PERSONALES_PCT_ALTO
}

export interface CapacidadPagoEstimada {
  monto: number
  cuota: number
  disponible: number
  capacidad: number
  gastosPersonales: number
}

/**
 * Replica la política de capacidad de pago del motor (PPT v4):
 * - Gastos personales automáticos según bandas de SMMLV.
 * - Disponible = ingreso - gastos personales.
 * - Capacidad de pago = disponible * 70%.
 * - Cupo = valor presente de la capacidad a 2% mensual y plazo dado.
 * - Tope máximo parametrizable: $20.000.000.
 *
 * El parámetro `egresosMensuales` se mantiene solo para compatibilidad
 * con pantallas heredadas; si es 0 o undefined se usa la fórmula del motor.
 */
export function calcularCupoSugerido(
  ingresosMensuales: number,
  plazoMeses: number,
  egresosMensuales?: number,
): CapacidadPagoEstimada {
  // Fallback legacy: si alguien aún pasa egresos reales, conservar el cálculo anterior.
  if (egresosMensuales != null && egresosMensuales > 0) {
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
    return {
      monto,
      cuota,
      disponible,
      capacidad: cuota,
      gastosPersonales: egresosMensuales,
    }
  }

  const ingresoSmmlv = ingresosMensuales / SMMLV
  const gastosPersonales = Math.round(
    ingresosMensuales * gastosPersonalesPct(ingresoSmmlv),
  )
  const disponible = Math.max(0, ingresosMensuales - gastosPersonales)
  const capacidad = Math.round(disponible * CAPACIDAD_PAGO_PCT)
  const monto = Math.min(
    CUPO_MAXIMO,
    Math.round(
      valorPresenteAnualidad(capacidad, TASA_MENSUAL_REFERENCIA, plazoMeses),
    ),
  )
  // Cuota que pagaría el cliente: anualidad + seguro de vida, como la
  // oferta real (oferta.cuota_mensual del backend la incluye igual).
  const cuota = Math.round(
    cuotaAnualidad(monto, TASA_MENSUAL_REFERENCIA, plazoMeses) +
      (monto * PRIMA_SEGURO_VIDA_PCT) / 100,
  )
  return { monto, cuota, disponible, capacidad, gastosPersonales }
}

/** Resultado local cuando el backend no está disponible. */
export function crearResultadoDemo({
  decision,
  ingresosMensuales,
  plazoMeses,
}: {
  decision: DecisionCredito
  ingresosMensuales: number
  plazoMeses: number
}): ResultadoEvaluacionCredito {
  const { monto, cuota } = calcularCupoSugerido(ingresosMensuales, plazoMeses)
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
