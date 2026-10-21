import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  AreaChart,
  Area,
  ReferenceLine,
} from 'recharts'
import Tarjeta from '../../shared/ui/Tarjeta'
import Skeleton from '../../shared/ui/Skeleton'
import { number } from '../../shared/lib/formatters'
import { useEsMovil } from '../../shared/lib/useEsMovil'

const TOOLTIP_ESTILO = {
  borderRadius: 12,
  border: '1px solid #e2e8f0',
  boxShadow: '0 4px 12px rgba(15,23,42,0.10)',
  fontSize: 12,
  padding: '8px 12px',
} as const

const TICK_ESTILO = { fontSize: 12, fill: '#64748b' } as const

export interface FiltroPanel {
  campo: 'estado' | 'ocupacion' | 'mes' | 'etapa'
  valor: string
  etiqueta: string
}

interface PuntoEstado {
  estado: string
  name: string
  value: number
  color: string
}

interface PuntoMes {
  range: string
  clave: string
  count: number
  anterior: number
}

interface GraficasResumenProps {
  cargando: boolean
  byStatus: PuntoEstado[]
  monthBuckets: PuntoMes[]
  totalAnimado: number
  filtro: FiltroPanel | null
  alternarFiltro: (f: FiltroPanel) => void
}

/** Las tres gráficas recharts del dashboard: chunk separado para que los
    KPIs pinten sin descargar la librería de gráficas. */
export default function GraficasResumen({
  cargando,
  byStatus,
  monthBuckets,
  totalAnimado,
  filtro,
  alternarFiltro,
}: GraficasResumenProps) {
  const esMovil = useEsMovil()
  const tickEje = esMovil ? { fontSize: 10, fill: '#64748b' } : TICK_ESTILO

  // Ticks redondos: 4 intervalos con paso "bonito" que cubra ambas
  // series (actual y periodo anterior) — el pico nunca queda cortado.
  const maxSerie = Math.max(
    4,
    ...monthBuckets.flatMap((b) => [b.count, b.anterior]),
  )
  const pasoY =
    [1, 2, 5, 10, 20, 25, 50, 100, 250, 500].find((t) => maxSerie <= t * 4) ??
    Math.ceil(maxSerie / 4)
  const topeY = pasoY * 4
  const ticksY = [0, pasoY, pasoY * 2, pasoY * 3, pasoY * 4]
  return (
    <>
      <Tarjeta>
        <h3 className="font-semibold text-slate-900 mb-4">
          Distribución por estado
        </h3>
        <div
          className="relative h-48 sm:h-56"
          aria-busy={cargando}
          role="img"
          aria-label={`Distribución por estado: ${byStatus.map((item) => `${item.name}: ${item.value}`).join(', ')}`}
        >
          {cargando ? (
            <Skeleton className="h-full w-full rounded-xl" />
          ) : (
            <>
              <ResponsiveContainer>
                <PieChart>
                  <Pie
                    data={byStatus}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={62}
                    outerRadius={88}
                    paddingAngle={3}
                    cornerRadius={6}
                    stroke="#ffffff"
                    strokeWidth={2}
                  >
                    {byStatus.map((s) => (
                      <Cell
                        key={s.name}
                        fill={s.color}
                        cursor="pointer"
                        opacity={
                          filtro?.campo === 'estado' &&
                          filtro.valor !== s.estado
                            ? 0.3
                            : 1
                        }
                        onClick={() =>
                          alternarFiltro({
                            campo: 'estado',
                            valor: s.estado,
                            etiqueta: s.name,
                          })
                        }
                      />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={TOOLTIP_ESTILO} />
                </PieChart>
              </ResponsiveContainer>
              <div className="pointer-events-none absolute inset-0 grid place-items-center">
                <div className="text-center">
                  <p className="text-2xl font-bold text-slate-900">
                    {number(Math.round(totalAnimado))}
                  </p>
                  <p className="text-[11px] uppercase tracking-wide text-slate-500">
                    solicitudes
                  </p>
                </div>
              </div>
            </>
          )}
        </div>
        {!cargando && (
          <ul className="mt-4 grid grid-cols-1 min-[420px]:grid-cols-2 gap-x-4 gap-y-2 text-xs text-slate-600">
            {byStatus.map((item) => {
              const activo =
                filtro?.campo === 'estado' && filtro.valor === item.estado
              return (
                <li key={item.name}>
                  <button
                    type="button"
                    onClick={() =>
                      alternarFiltro({
                        campo: 'estado',
                        valor: item.estado,
                        etiqueta: item.name,
                      })
                    }
                    className={`flex w-full items-center gap-2 rounded-md px-1.5 py-1 text-left transition hover:bg-slate-50 ${
                      activo ? 'bg-slate-100 ring-1 ring-slate-300' : ''
                    }`}
                    aria-pressed={activo}
                  >
                    <span
                      className="h-2.5 w-2.5 shrink-0 rounded-full"
                      style={{ backgroundColor: item.color }}
                    />
                    <span className="truncate">{item.name}</span>
                    <span className="ml-auto font-semibold text-slate-900">
                      {item.value}
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </Tarjeta>

      <Tarjeta className="order-last lg:col-span-2">
        <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="font-semibold text-slate-900">Últimos 6 meses</h3>
          {/* Leyenda honesta: las dos series comparten eje y ventana. */}
          <div className="flex items-center gap-4 text-xs text-slate-500">
            <span className="flex items-center gap-1.5">
              <span className="h-0.5 w-4 rounded-full bg-brand-500" />
              Este periodo
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-0.5 w-4 rounded-full bg-slate-300" />6 meses
              anteriores
            </span>
          </div>
        </div>
        <div
          className="h-52 sm:h-64"
          aria-busy={cargando}
          role="img"
          aria-label={`Solicitudes en los últimos seis meses: ${monthBuckets.map((item) => `${item.range}: ${item.count}`).join(', ')}`}
        >
          {cargando ? (
            <Skeleton className="h-full w-full rounded-xl" />
          ) : (
            <ResponsiveContainer>
              <AreaChart
                data={monthBuckets}
                margin={{
                  top: 12,
                  right: esMovil ? 8 : 16,
                  bottom: 0,
                  left: 0,
                }}
                onClick={(estado) => {
                  const p = estado?.activePayload?.[0]?.payload as
                    { clave?: string; range?: string } | undefined
                  if (p?.clave)
                    alternarFiltro({
                      campo: 'mes',
                      valor: p.clave,
                      etiqueta: `Mes ${p.range}`,
                    })
                }}
                className="cursor-pointer"
              >
                <defs>
                  <linearGradient
                    id="gradSolicitudes"
                    x1="0"
                    y1="0"
                    x2="0"
                    y2="1"
                  >
                    <stop offset="0%" stopColor="#099dd7" stopOpacity={0.35} />
                    <stop
                      offset="100%"
                      stopColor="#099dd7"
                      stopOpacity={0.02}
                    />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="#e2e8f0"
                  vertical={false}
                />
                <XAxis
                  dataKey="range"
                  tick={tickEje}
                  tickLine={false}
                  axisLine={{ stroke: '#cbd5e1' }}
                />
                <YAxis
                  tick={tickEje}
                  tickLine={false}
                  axisLine={false}
                  allowDecimals={false}
                  domain={[0, topeY]}
                  ticks={ticksY}
                  width={esMovil ? 24 : 40}
                />
                <Tooltip
                  contentStyle={TOOLTIP_ESTILO}
                  cursor={{ stroke: '#099dd7', strokeDasharray: '3 3' }}
                />
                {filtro?.campo === 'mes' && (
                  <ReferenceLine
                    x={
                      monthBuckets.find((b) => b.clave === filtro.valor)?.range
                    }
                    stroke="#087ead"
                    strokeWidth={2}
                    strokeDasharray="4 3"
                  />
                )}
                <Area
                  type="monotone"
                  dataKey="anterior"
                  name="6 meses anteriores"
                  stroke="#94a3b8"
                  strokeWidth={1.5}
                  strokeDasharray="5 4"
                  fill="none"
                  dot={false}
                  activeDot={{ r: 3.5, fill: '#64748b', strokeWidth: 0 }}
                />
                <Area
                  type="monotone"
                  dataKey="count"
                  name="Solicitudes"
                  stroke="#099dd7"
                  strokeWidth={2.5}
                  fill="url(#gradSolicitudes)"
                  dot={false}
                  activeDot={{ r: 4, fill: '#087ead', strokeWidth: 0 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </Tarjeta>
    </>
  )
}
