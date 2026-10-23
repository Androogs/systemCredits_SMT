import { useQuery } from '@tanstack/react-query'
import { AlertCircle } from 'lucide-react'
import Tarjeta from '../../shared/ui/Tarjeta'
import { currency, number } from '../../shared/lib/formatters'
import {
  obtenerMetricasEmbudo,
  type MetricasEmbudoApi,
} from '../../features/credit-origination/api/originacionApi'
import type { FiltroPanel } from './GraficasResumen'

const REFRESCO_MS = 30_000

// Rampa de la marca: la etapa más temprana es la más ancha y la más
// saturada; el azul se apaga conforme cae la conversión.
const TONOS_ETAPA = [
  'bg-[#087ead]',
  'bg-[#099dd7]',
  'bg-[#1cb6ea]',
  'bg-[#5fcbf0]',
  'bg-[#176b46]',
]

interface PropsEmbudo {
  vistaBinaria: boolean
  /** Rango de radicación (filtro de mes del panel); undefined = global. */
  rango?: { desde: string; hasta: string } | null
  /** Filtros dimensionales del panel (solo admin los envía). */
  concesionarioId?: number
  asesorId?: number
  filtro: FiltroPanel | null
  /** Click en una etapa → la lista se filtra a ese hito. */
  onFiltrar: (claveEtapa: string) => void
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
  return (
    <div className="space-y-3">
      {metricas.etapas.map((etapa, i) => {
        const anterior = i > 0 ? metricas.etapas[i - 1].total : 0
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
            className={`relative flex w-full items-center gap-x-3 rounded-lg px-3 pb-3 pt-2 text-left transition hover:bg-slate-50 ${
              activo
                ? 'bg-brand-500/[.07] ring-1 ring-inset ring-brand-500/25'
                : ''
            } ${hayFiltroEtapa && !activo ? 'opacity-50' : ''}`}
          >
            <span className="min-w-0 flex-1 truncate text-left text-sm text-slate-700">
              {etapa.etiqueta}
            </span>
            <span className="shrink-0 text-sm font-semibold tabular-nums text-slate-900">
              {number(etapa.total)}
            </span>
            <span className="w-20 shrink-0 text-right text-xs text-slate-500 tabular-nums">
              {conversion != null ? `${conversion}% etapa` : `${etapa.pct}%`}
            </span>
            {/* Magnitud como track delgado al borde inferior, proporcional
                a la etapa mayor (patrón share-bar). */}
            <span
              aria-hidden="true"
              className="absolute inset-x-3 bottom-1 h-[3px] rounded-full bg-slate-100"
            >
              {etapa.total > 0 && (
                <span
                  className={`block h-full rounded-full ${TONOS_ETAPA[i] ?? TONOS_ETAPA[0]}`}
                  style={{
                    width: `${Math.max((etapa.total / max) * 100, 4)}%`,
                  }}
                />
              )}
            </span>
          </button>
        )
      })}
      {metricas.canceladas > 0 && (
        <p className="pt-1 text-xs text-slate-500">
          {number(metricas.canceladas)} cancelada
          {metricas.canceladas === 1 ? '' : 's'} en el camino.
        </p>
      )}
    </div>
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
            <th className="pb-2 text-right font-medium">Desembolsadas</th>
            <th className="pb-2 text-right font-medium">Valor girado</th>
          </tr>
        </thead>
        <tbody>
          {metricas.por_aliado.map((fila) => (
            <tr key={fila.aliado} className="border-t border-slate-50">
              <td className="py-2 font-medium text-slate-700">{fila.aliado}</td>
              <td className="py-2 text-right text-slate-600 tabular-nums">
                {number(fila.con_oferta)}
              </td>
              <td className="py-2 text-right text-slate-600 tabular-nums">
                {number(fila.formalizadas)}
              </td>
              <td className="py-2 text-right font-semibold text-slate-900 tabular-nums">
                {number(fila.desembolsadas)}
              </td>
              <td className="py-2 text-right text-slate-600 tabular-nums">
                {currency(Number(fila.valor_desembolsado))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Embudo originación → desembolso: conteos reales del servidor (el
    listado del panel solo trae 200 filas). Se refresca cada 30 s, se
    acota al mes del filtro global y cada etapa filtra la tabla. La
    tabla por aliado es de negocio: solo la ve el administrador. */
export default function EmbudoOriginacion({
  vistaBinaria,
  rango,
  concesionarioId,
  asesorId,
  filtro,
  onFiltrar,
}: PropsEmbudo) {
  const { data, isPending, error } = useQuery({
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

  return (
    <Tarjeta>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold text-slate-900">Embudo de originación</h3>
        {data && (
          <span className="text-xs text-slate-500">
            {number(data.radicadas)} solicitudes radicadas
            {rango ? ' en el periodo' : ''}
          </span>
        )}
      </div>
      {isPending ? (
        <div className="space-y-3" aria-busy="true" aria-hidden="true">
          {[100, 85, 70, 55].map((w) => (
            <div
              key={w}
              className="h-9 animate-pulse rounded-lg bg-slate-200"
              style={{ width: `${w}%` }}
            />
          ))}
        </div>
      ) : error ? (
        <p className="flex items-center gap-2 py-6 text-sm text-red-700">
          <AlertCircle size={16} aria-hidden="true" />
          No fue posible cargar las métricas del embudo.
        </p>
      ) : data ? (
        <>
          <BarrasEmbudo metricas={data} filtro={filtro} onFiltrar={onFiltrar} />
          {!vistaBinaria && <TablaAliados metricas={data} />}
        </>
      ) : null}
    </Tarjeta>
  )
}
