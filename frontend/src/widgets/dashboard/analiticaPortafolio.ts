import { SEDES_POR_MARCA } from '../../features/credit-origination/model/concesionarios'
import { coincideMarcaSede } from './BarraFiltrosDimensionales'
import {
  numero,
  OCUPACION_LABELS,
  PERFIL_INGRESO_LABELS,
  TIPO_CONTRATO_LABELS,
  estadoParaVista,
  ESTADOS_POSITIVOS_VISTA,
} from '../../entities/credit/model/solicitudesPanel'
import type { SolicitudResumenApi } from '../../features/credit-origination/api/originacionApi'

export const MARCAS_CATALOGO = Object.keys(SEDES_POR_MARCA)
export const SIN_MARCA = 'Sin marca asignada'

/** Marca del concesionario que radicó: los nombres vienen como
    "<Marca> <Sede>". Solo cuentan las del catálogo; sin sede o con
    una sede fuera del catálogo se agrupa como "sin marca". */
export function marcaDe(nombre: string | null | undefined): string {
  if (!nombre) return SIN_MARCA
  return MARCAS_CATALOGO.find((m) => coincideMarcaSede(nombre, m)) ?? SIN_MARCA
}

export type Rango = [label: string, test: (v: number) => boolean]

// Rangos de la distribución monetaria, plazo y continuidad laboral.
export const RANGOS_MONTO: Rango[] = [
  ['< $5 M', (v) => v < 5e6],
  ['$5–10 M', (v) => v >= 5e6 && v < 10e6],
  ['$10–15 M', (v) => v >= 10e6 && v < 15e6],
  ['$15–20 M', (v) => v >= 15e6 && v < 20e6],
  ['≥ $20 M', (v) => v >= 20e6],
]
export const RANGOS_PLAZO: Rango[] = [
  ['< 12', (v) => v < 12],
  ['12–24', (v) => v >= 12 && v < 24],
  ['24–36', (v) => v >= 24 && v < 36],
  ['36–48', (v) => v >= 36 && v < 48],
  ['≥ 48', (v) => v >= 48],
]
export const RANGOS_CUOTA: Rango[] = [
  ['< $250 mil', (v) => v < 250e3],
  ['$250–500 mil', (v) => v >= 250e3 && v < 500e3],
  ['$500–750 mil', (v) => v >= 500e3 && v < 750e3],
  ['$750 mil–$1 M', (v) => v >= 750e3 && v < 1e6],
  ['≥ $1 M', (v) => v >= 1e6],
]
export const RANGOS_CONTINUIDAD: Rango[] = [
  ['0', (v) => v === 0],
  ['1–5', (v) => v >= 1 && v <= 5],
  ['6–11', (v) => v >= 6 && v <= 11],
  ['≥ 12', (v) => v >= 12],
]

/** Reparte valores numéricos en los rangos dados, conservando el orden
    del catálogo; `sinDato` agrega un último segmento para los nulos.
    Los rangos vacíos se omiten (la lista queda solo con producción). */
export function distribuir(
  valores: (number | null | undefined)[],
  rangos: Rango[],
  sinDato: string | null = null,
): { label: string; valor: number }[] {
  const conteo = new Map<string, number>(rangos.map(([l]) => [l, 0]))
  if (sinDato) conteo.set(sinDato, 0)
  for (const v of valores) {
    const label =
      v == null ? sinDato : (rangos.find(([, t]) => t(v))?.[0] ?? null)
    if (label) conteo.set(label, (conteo.get(label) ?? 0) + 1)
  }
  return [...conteo.entries()]
    .map(([label, valor]) => ({ label, valor }))
    .filter((i) => i.valor > 0)
}

export function promedio(vs: number[]): number | null {
  return vs.length ? vs.reduce((a, b) => a + b, 0) / vs.length : null
}

/** Agregados del portafolio para los paneles analíticos: mismas
    cuentas que usa el Resumen del admin, calculadas sobre el listado
    ya acotado por los filtros dimensionales. */
export function agregadosPortafolio(base: SolicitudResumenApi[]) {
  const conteoMarca = base.reduce<Record<string, number>>((acc, s) => {
    const marca = marcaDe(s.nombre_concesionario)
    acc[marca] = (acc[marca] ?? 0) + 1
    return acc
  }, {})
  const porMarca = [
    ...MARCAS_CATALOGO.map((label) => ({
      label,
      valor: conteoMarca[label] ?? 0,
    })).sort((a, b) => b.valor - a.valor || a.label.localeCompare(b.label)),
    ...(conteoMarca[SIN_MARCA]
      ? [{ label: SIN_MARCA, valor: conteoMarca[SIN_MARCA] }]
      : []),
  ]

  const porScore = Object.entries(
    base.reduce<Record<string, number>>((acc, s) => {
      const p = s.evaluacion?.perfil_score
      if (!p) return acc
      acc[p] = (acc[p] ?? 0) + 1
      return acc
    }, {}),
  )
    .map(([perfil, valor]) => ({ label: `Perfil ${perfil}`, valor }))
    .sort((a, b) => a.label.localeCompare(b.label))

  const conteoIngreso = base.reduce<Record<string, number>>((acc, s) => {
    const p = s.evaluacion?.perfil_ingreso
    if (p) acc[p] = (acc[p] ?? 0) + 1
    return acc
  }, {})
  const porIngreso = Object.keys(PERFIL_INGRESO_LABELS)
    .concat(
      Object.keys(conteoIngreso).filter((k) => !(k in PERFIL_INGRESO_LABELS)),
    )
    .map((k) => ({
      label: PERFIL_INGRESO_LABELS[k] ?? k,
      valor: conteoIngreso[k] ?? 0,
    }))
    .filter((i) => i.valor > 0)

  const conteoContrato = base.reduce<Record<string, number>>((acc, s) => {
    const k = s.tipo_contrato || 'sin_dato'
    acc[k] = (acc[k] ?? 0) + 1
    return acc
  }, {})
  const porTipoContrato = Object.keys(TIPO_CONTRATO_LABELS)
    .concat('sin_dato')
    .map((k) => ({
      label: k === 'sin_dato' ? 'Sin dato' : (TIPO_CONTRATO_LABELS[k] ?? k),
      valor: conteoContrato[k] ?? 0,
    }))
    .filter((i) => i.valor > 0)

  const porContinuidad = distribuir(
    base.map((s) => s.meses_continuidad ?? null),
    RANGOS_CONTINUIDAD,
    'Sin dato',
  )

  const porOcupacion = Object.entries(OCUPACION_LABELS)
    .map(([tipo, label]) => {
      const grupo = base.filter((s) => s.ocupacion === tipo)
      const aprobadas = grupo.filter((s) =>
        ESTADOS_POSITIVOS_VISTA.has(estadoParaVista(s)),
      ).length
      const rechazadas = grupo.filter(
        (s) => estadoParaVista(s) === 'RECHAZADO',
      ).length
      return {
        tipo,
        label,
        total: grupo.length,
        aprobadas,
        rechazadas,
        otras: grupo.length - aprobadas - rechazadas,
      }
    })
    .filter((g) => g.total > 0)

  // Rangos monetarios: promedio sobre las solicitudes que tienen el
  // dato (cupo aprobado / oferta elegida); el share usa ese subtotal.
  const montos = base
    .filter((s) => ESTADOS_POSITIVOS_VISTA.has(estadoParaVista(s)))
    .map((s) => numero(s.evaluacion?.cupo_sugerido))
    .filter((n): n is number => n != null)
  const cuotas = base
    .map((s) => numero(s.cuota_total))
    .filter((n): n is number => n != null)
  const plazos = base
    .map((s) => s.plazo_deseado_meses)
    .filter((n): n is number => n != null)

  return {
    porMarca,
    porScore,
    porIngreso,
    porTipoContrato,
    porContinuidad,
    porOcupacion,
    montos,
    cuotas,
    plazos,
    promMonto: promedio(montos),
    promCuota: promedio(cuotas),
    promPlazo: promedio(plazos),
    porMonto: distribuir(montos, RANGOS_MONTO),
    porCuota: distribuir(cuotas, RANGOS_CUOTA),
    porPlazoRangos: distribuir(
      base.map((s) => s.plazo_deseado_meses ?? null),
      RANGOS_PLAZO,
      'Sin plazo',
    ),
  }
}
