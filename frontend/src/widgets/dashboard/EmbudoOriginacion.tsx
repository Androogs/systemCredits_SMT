import { lazy, Suspense } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertCircle } from 'lucide-react'
import Tarjeta from '../../shared/ui/Tarjeta'
import Skeleton from '../../shared/ui/Skeleton'
import { number } from '../../shared/lib/formatters'
import {
  obtenerMetricasEmbudo,
  type EmbudoCausalApi,
  type MetricasEmbudoApi,
} from '../../features/credit-origination/api/originacionApi'
import type { FiltroPanel } from './GraficasResumen'

// Recharts solo se descarga cuando hay datos de asesor que graficar.
const RankingAsesores = lazy(() => import('./RankingAsesores'))

const REFRESCO_MS = 30_000

// Barras horizontales teal (etapas) y columnas coral (causales),
// siguiendo el patrón de referencia del embudo.
const TONO_BARRA = 'bg-teal-500'
const TONO_CAUSAL = 'bg-rose-400'

/** Parámetros de alcance de las métricas del embudo: el rango del filtro
    de mes y los filtros dimensionales del panel (solo admin los envía). */
interface AlcanceMetricas {
  rango?: { desde: string; hasta: string } | null
  concesionarioId?: number
  asesorId?: number
}

interface PropsEmbudo extends AlcanceMetricas {
  vistaBinaria: boolean
  filtro: FiltroPanel | null
  /** Click en una etapa → la lista se filtra a ese hito. */
  onFiltrar: (claveEtapa: string) => void
}

/** Métricas del embudo compartidas por las tarjetas del resumen: la misma
    queryKey deduplica la petición entre embudo, top asesores y causales. */
function useMetricasEmbudo({
  rango,
  concesionarioId,
  asesorId,
}: AlcanceMetricas) {
  return useQuery({
    queryKey: [
      'metricas-embudo',
      rango?.desde ?? null,
      rango?.hasta ?? null,
      concesionarioId ?? null,
      asesorId ?? null,
    ],
    queryFn: () =>
      obtenerMetricasEmbudo({
        desde: rango?.desde,
        hasta: rango?.hasta,
        id_concesionario: concesionarioId,
        id_asesor: asesorId,
      }),
    refetchInterval: REFRESCO_MS,
  })
}

function BarrasEmbudo({
  metricas,
  filtro,
  onFiltrar,
}: {
  metricas: MetricasEmbudoApi
  filtro: FiltroPanel | null
  onFiltrar: (claveEtapa: string) => void
}) {
  const max = metricas.radicadas || 1
  // La etapa de desembolso no se muestra: es mecánica de financiera y
  // la base compartida cierra el ciclo en la formalización.
  const etapas = metricas.etapas.filter((e) => e.clave !== 'desembolsadas')
  return (
    <div>
      <div className="space-y-6">
        {etapas.map((etapa, i) => {
          const anterior = i > 0 ? etapas[i - 1].total : 0
          const conversion =
            i > 0 && anterior > 0
              ? Math.round((etapa.total / anterior) * 100)
              : null
          const activo =
            (filtro?.campo === 'etapa' && filtro.valor === etapa.clave) ||
            (etapa.clave === 'aprobadas' &&
              filtro?.campo === 'estado' &&
              filtro.valor === 'APROBADO')
          const hayFiltroEtapa =
            filtro != null &&
            (filtro.campo === 'etapa' || filtro.campo === 'estado')
          const ancho = Math.min(100, Math.round((etapa.total / max) * 100))
          return (
            <button
              key={etapa.clave}
              type="button"
              onClick={() => onFiltrar(etapa.clave)}
              aria-pressed={activo}
              title={
                etapa.clave === 'radicadas'
                  ? 'Ver todas las solicitudes'
                  : `Filtrar solicitudes: ${etapa.etiqueta}`
              }
              className={`block w-full rounded-lg px-2 py-1.5 text-left transition hover:bg-slate-50 ${
                activo
                  ? 'bg-brand-500/[.07] ring-1 ring-inset ring-brand-500/25'
                  : ''
              } ${hayFiltroEtapa && !activo ? 'opacity-50' : ''}`}
            >
              <span className="flex items-baseline justify-between gap-3">
                <span className="truncate text-sm text-slate-700">
                  {etapa.etiqueta}
                </span>
                <span className="flex shrink-0 items-baseline gap-4 tabular-nums">
                  <strong className="text-base font-bold text-slate-900">
                    {number(etapa.total)}
                  </strong>
                  <span className="w-16 text-right text-xs text-slate-400">
                    {conversion != null
                      ? `${conversion}% etapa`
                      : `${etapa.pct}%`}
                  </span>
                </span>
              </span>
              {/* Magnitud como barra horizontal proporcional a radicadas. */}
              <span
                aria-hidden="true"
                className="mt-1.5 block h-1.5 w-full rounded-full bg-slate-100"
              >
                {etapa.total > 0 && (
                  <span
                    className={`block h-full rounded-full ${TONO_BARRA}`}
                    style={{ width: `${Math.max(ancho, 1.5)}%` }}
                  />
                )}
              </span>
            </button>
          )
        })}
      </div>
      {metricas.canceladas > 0 && (
        <p className="pt-2 text-xs text-slate-500">
          {number(metricas.canceladas)} cancelada
          {metricas.canceladas === 1 ? '' : 's'} en el camino.
        </p>
      )}
    </div>
  )
}

/** Tope redondo del eje Y: 4 divisiones sobre el máximo. */
function _ticksEje(max: number): number[] {
  const paso = Math.max(1, Math.ceil(max / 4))
  return [4, 3, 2, 1, 0].map((i) => i * paso)
}

function CausalesRechazo({
  causales,
  totalRechazadas,
}: {
  causales: EmbudoCausalApi[]
  totalRechazadas: number
}) {
  const max = causales[0].total || 1
  const ticks = _ticksEje(max)
  const techo = ticks[0] || 1
  // Columnas del borde cuyo tooltip centrado se saldría de la tarjeta.
  const borde = Math.ceil(causales.length * 0.15)
  return (
    <div className="flex">
      {/* Eje Y con sus ticks. */}
      <div
        aria-hidden="true"
        className="flex h-28 w-7 flex-col justify-between pr-1 text-right text-[10px] tabular-nums leading-none text-slate-400"
      >
        {ticks.map((t) => (
          <span key={t}>{t}</span>
        ))}
      </div>
      <div className="min-w-0 flex-1">
        <div className="relative h-28 border-b border-slate-200">
          {/* Líneas guía del eje. */}
          {ticks.slice(1, -1).map((t) => (
            <div
              key={t}
              aria-hidden="true"
              className="absolute inset-x-0 border-t border-dashed border-slate-100"
              style={{ bottom: `${(t / techo) * 100}%` }}
            />
          ))}
          <div className="absolute inset-0 flex items-end gap-[2px] sm:gap-1">
            {causales.map((causal, i) => {
              const alineacion =
                i < borde
                  ? 'left-0'
                  : i >= causales.length - borde
                    ? 'right-0'
                    : 'left-1/2 -translate-x-1/2'
              const piquito =
                i < borde
                  ? 'left-3'
                  : i >= causales.length - borde
                    ? 'right-3'
                    : 'left-1/2 -translate-x-1/2'
              return (
                <div
                  key={causal.codigo}
                  className="group relative flex h-full min-w-0 flex-1 items-end"
                >
                  {/* Tooltip propio: las barras son demasiado angostas
                      para depender del title nativo del navegador. */}
                  <div
                    className={`pointer-events-none absolute bottom-full z-20 mb-2 hidden w-44 rounded-xl border border-slate-200 bg-white px-3 py-2 text-left text-xs shadow-lg group-hover:block ${alineacion}`}
                  >
                    <p className="font-semibold text-slate-900">
                      {causal.descripcion}
                      <span className="font-normal text-slate-400">
                        {' '}
                        · {causal.codigo}
                      </span>
                    </p>
                    <p className="mt-0.5 text-slate-600">
                      Rechazadas: {number(causal.total)} (
                      {totalRechazadas > 0
                        ? Math.round((causal.total / totalRechazadas) * 100)
                        : 0}
                      %)
                    </p>
                    <span
                      aria-hidden="true"
                      className={`absolute top-full h-2 w-2 -translate-y-1 rotate-45 border-b border-r border-slate-200 bg-white ${piquito}`}
                    />
                  </div>
                  <div
                    className={`w-full rounded-t-sm transition-colors ${TONO_CAUSAL} group-hover:bg-rose-500`}
                    style={{
                      height: `${Math.max((causal.total / techo) * 100, 4)}%`,
                    }}
                  />
                </div>
              )
            })}
          </div>
        </div>
        {/* Etiquetas: con pocas causales van inclinadas; con muchas
            (>12) pasan a escritura vertical para no encimarse. El
            padding reserva el alto que ocupan. */}
        <div
          className={`flex gap-[2px] sm:gap-1 ${causales.length > 12 ? 'pb-24' : 'pb-12'}`}
        >
          {causales.map((causal) => (
            <div
              key={causal.codigo}
              className={`flex min-w-0 flex-1 overflow-visible ${
                causales.length > 12 ? 'justify-center' : 'justify-end'
              }`}
            >
              <span
                className={
                  causales.length > 12
                    ? 'block h-24 w-3 truncate whitespace-nowrap text-[10px] text-slate-500 [writing-mode:vertical-rl]'
                    : 'block w-16 origin-top-right -rotate-45 translate-x-2 translate-y-1 truncate text-[10px] leading-tight text-slate-500'
                }
                title={causal.descripcion}
              >
                {causal.descripcion}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function RescateReevaluacion({ metricas }: { metricas: MetricasEmbudoApi }) {
  const { reevaluadas, rescatadas } = metricas.reevaluacion
  if (reevaluadas === 0) {
    return null
  }
  const pct = Math.round((rescatadas / reevaluadas) * 100)
  return (
    <div className="mt-3 flex flex-wrap items-baseline gap-x-4 gap-y-1 rounded-lg bg-slate-50 px-3 py-2">
      <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
        Re-evaluación
      </span>
      <span className="text-sm text-slate-700">
        <strong className="font-semibold">{number(reevaluadas)}</strong>{' '}
        {reevaluadas === 1 ? 'rectificada' : 'rectificadas'}
      </span>
      <span className="text-sm text-slate-700">
        <strong className="font-semibold text-[#176b46]">
          {number(rescatadas)}
        </strong>{' '}
        {rescatadas === 1 ? 'rescatada' : 'rescatadas'} ({pct}%)
      </span>
    </div>
  )
}

function TablaAsesores({ metricas }: { metricas: MetricasEmbudoApi }) {
  if (metricas.por_asesor.length === 0) {
    return null
  }
  return (
    <details className="group mt-3">
      <summary className="cursor-pointer select-none text-xs font-medium uppercase tracking-wide text-slate-500 transition hover:text-slate-700 [&::-webkit-details-marker]:hidden">
        Tabla completa · {number(metricas.por_asesor.length)}{' '}
        {metricas.por_asesor.length === 1 ? 'persona' : 'personas'}{' '}
        <span className="text-slate-400 group-open:hidden">+</span>
        <span className="hidden text-slate-400 group-open:inline">−</span>
      </summary>
      <div className="mt-2 max-h-80 overflow-y-auto overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="pb-2 font-medium">Asesor</th>
              <th className="pb-2 text-right font-medium">Radicadas</th>
              <th className="pb-2 text-right font-medium">Aprobadas</th>
              <th className="pb-2 text-right font-medium">% aprob.</th>
            </tr>
          </thead>
          <tbody>
            {metricas.por_asesor.map((fila, i) => (
              <tr
                key={fila.cedula ?? `sin-cedula-${i}`}
                className="border-t border-slate-50"
              >
                <td className="py-2 font-medium text-slate-700">
                  <span className={fila.titular_anterior ? 'italic' : ''}>
                    {fila.asesor}
                  </span>
                  {fila.cedula && (
                    <span className="block text-xs font-normal text-slate-400">
                      CC {fila.cedula}
                    </span>
                  )}
                </td>
                <td className="py-2 text-right text-slate-600 tabular-nums">
                  {number(fila.radicadas)}
                </td>
                <td className="py-2 text-right text-slate-600 tabular-nums">
                  {number(fila.aprobadas)}
                </td>
                <td className="py-2 text-right font-semibold text-slate-900 tabular-nums">
                  {fila.radicadas > 0
                    ? `${Math.round((fila.aprobadas / fila.radicadas) * 100)}%`
                    : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}

function TablaAliados({ metricas }: { metricas: MetricasEmbudoApi }) {
  if (metricas.por_aliado.length === 0) {
    return (
      <p className="mt-4 border-t border-slate-100 pt-3 text-xs text-slate-500">
        Aún no hay solicitudes con oferta seleccionada; el desglose por aliado
        aparece cuando el cliente elige financiación.
      </p>
    )
  }
  return (
    <div className="mt-4 overflow-x-auto border-t border-slate-100 pt-3">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
            <th className="pb-2 font-medium">Aliado</th>
            <th className="pb-2 text-right font-medium">Con oferta</th>
            <th className="pb-2 text-right font-medium">Formalizadas</th>
          </tr>
        </thead>
        <tbody>
          {metricas.por_aliado.map((fila) => (
            <tr key={fila.aliado} className="border-t border-slate-50">
              <td className="py-2 font-medium text-slate-700">{fila.aliado}</td>
              <td className="py-2 text-right text-slate-600 tabular-nums">
                {number(fila.con_oferta)}
              </td>
              <td className="py-2 text-right font-semibold text-slate-900 tabular-nums">
                {number(fila.formalizadas)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function EstadoCarga({ alto = 'h-36' }: { alto?: string }) {
  return (
    <div
      className={`flex ${alto} items-end gap-3`}
      aria-busy="true"
      aria-hidden="true"
    >
      {[100, 75, 45, 20].map((h) => (
        <div
          key={h}
          className="flex-1 animate-pulse rounded-md bg-slate-200"
          style={{ height: `${h}%` }}
        />
      ))}
    </div>
  )
}

function EstadoError({ texto }: { texto: string }) {
  return (
    <p className="flex items-center gap-2 py-6 text-sm text-red-700">
      <AlertCircle size={16} aria-hidden="true" />
      {texto}
    </p>
  )
}

/** Embudo originación → formalización: conteos reales del servidor
    (el listado del panel solo trae 200 filas). Se refresca cada 30 s,
    se acota al mes del filtro global y cada etapa filtra la tabla.
    El desglose por aliado es de negocio: no lo ve el asesor. */
export default function EmbudoOriginacion({
  vistaBinaria,
  rango,
  concesionarioId,
  asesorId,
  filtro,
  onFiltrar,
}: PropsEmbudo) {
  const { data, isPending, error } = useMetricasEmbudo({
    rango,
    concesionarioId,
    asesorId,
  })

  return (
    <Tarjeta>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold text-slate-900">Embudo de conversión</h3>
        {data && (
          <span className="text-xs text-slate-500">
            {number(data.radicadas)} solicitudes radicadas
            {rango ? ' en el periodo' : ''}
          </span>
        )}
      </div>
      {isPending ? (
        <EstadoCarga />
      ) : error ? (
        <EstadoError texto="No fue posible cargar las métricas del embudo." />
      ) : data ? (
        <>
          <BarrasEmbudo metricas={data} filtro={filtro} onFiltrar={onFiltrar} />
          {!vistaBinaria && (
            <>
              <RescateReevaluacion metricas={data} />
              <TablaAliados metricas={data} />
            </>
          )}
        </>
      ) : null}
    </Tarjeta>
  )
}

/** Top 5 de producción por asesor: radicadas con la composición
    aprobadas / resto y la tabla completa colapsable debajo. */
export function PanelTopAsesores({
  rango,
  concesionarioId,
  asesorId,
}: AlcanceMetricas) {
  const { data, isPending, error } = useMetricasEmbudo({
    rango,
    concesionarioId,
    asesorId,
  })

  return (
    <Tarjeta>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold text-slate-900">Top 5 asesores</h3>
        {data && data.por_asesor.length > 0 && (
          <span className="text-xs text-slate-500">
            {number(data.por_asesor.length)}{' '}
            {data.por_asesor.length === 1 ? 'persona' : 'personas'} con
            producción
          </span>
        )}
      </div>
      {isPending ? (
        <EstadoCarga alto="h-48" />
      ) : error ? (
        <EstadoError texto="No fue posible cargar la producción por asesor." />
      ) : data && data.por_asesor.length > 0 ? (
        <>
          <Suspense fallback={<Skeleton className="h-48 w-full rounded-xl" />}>
            <RankingAsesores asesores={data.por_asesor} top={5} />
          </Suspense>
          <TablaAsesores metricas={data} />
        </>
      ) : (
        <p className="py-10 text-center text-sm text-slate-500">
          Aún no hay producción registrada por asesor.
        </p>
      )}
    </Tarjeta>
  )
}

/** Causales de rechazo del motor: solo el administrador las recibe
    (el backend devuelve la lista vacía al resto de roles). */
export function PanelCausalesRechazo({
  rango,
  concesionarioId,
  asesorId,
}: AlcanceMetricas) {
  const { data, isPending, error } = useMetricasEmbudo({
    rango,
    concesionarioId,
    asesorId,
  })

  return (
    <Tarjeta>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold text-slate-900">Causales de rechazo</h3>
        {data && data.por_causal.length > 0 && (
          <span className="text-xs text-slate-500">
            {number(data.por_estado['rechazada'] ?? 0)} solicitudes rechazadas
          </span>
        )}
      </div>
      {isPending ? (
        <EstadoCarga alto="h-28" />
      ) : error ? (
        <EstadoError texto="No fue posible cargar las causales de rechazo." />
      ) : data && data.por_causal.length > 0 ? (
        <CausalesRechazo
          causales={data.por_causal}
          totalRechazadas={data.por_estado['rechazada'] ?? 0}
        />
      ) : (
        <p className="py-10 text-center text-sm text-slate-500">
          No hay solicitudes rechazadas en el periodo.
        </p>
      )}
    </Tarjeta>
  )
}
