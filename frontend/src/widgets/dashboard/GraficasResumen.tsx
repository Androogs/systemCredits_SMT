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
import NumeroFluido from '../../shared/ui/NumeroFluido'
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

interface DonaEstadosProps {
  cargando: boolean
  byStatus: PuntoEstado[]
  total: number
  filtro: FiltroPanel | null
  alternarFiltro: (f: FiltroPanel) => void
}

interface TendenciaSeisMesesProps {
  cargando: boolean
  monthBuckets: PuntoMes[]
  filtro: FiltroPanel | null
  alternarFiltro: (f: FiltroPanel) => void
}

/** Dona de distribución por decisión: cada segmento filtra el panel.
    Vive en chunk separado para que los KPIs pinten sin recharts. */
export function DonaEstados({
  cargando,
  byStatus,
  total,
  filtro,
  alternarFiltro,
}: DonaEstadosProps) {
  // Porcentaje sobre lo que pinta la dona (suma de sus segmentos), para
  // que los tres valores siempre sumen ~100 %.
  const totalDona = byStatus.reduce((a, s) => a + s.value, 0)
  const porcentaje = (valor: number) =>
    totalDona > 0 ? `${Math.round((valor / totalDona) * 100)}%` : '0%'

  return (
    // Ocupa todo el alto de la fila (lo fija el embudo vecino): la dona
    // crece con el espacio disponible y la leyenda queda al pie.
    <Tarjeta className="flex h-full flex-col">
      <h3 className="font-semibold text-slate-900 mb-2">
        Distribución de decisiones
      </h3>
      <div
        className="relative min-h-[16rem] flex-1 sm:min-h-[18rem]"
        aria-busy={cargando}
        role="img"
        aria-label={`Distribución por estado: ${byStatus.map((item) => `${item.name}: ${item.value} (${porcentaje(item.value)})`).join(', ')}`}
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
                  innerRadius="45%"
                  outerRadius="65%"
                  paddingAngle={3}
                  cornerRadius={6}
                  stroke="#ffffff"
                  strokeWidth={2}
                  labelLine={false}
                  label={({ cx, cy, midAngle, outerRadius, value, fill }) => {
                    if (!value) return null
                    const rad = (Math.PI / 180) * -(midAngle ?? 0)
                    const r = Number(outerRadius) + 16
                    const x = Number(cx) + r * Math.cos(rad)
                    const y = Number(cy) + r * Math.sin(rad)
                    return (
                      <text
                        x={x}
                        y={y}
                        fill={fill}
                        fontSize={14}
                        fontWeight={700}
                        textAnchor={x >= Number(cx) ? 'start' : 'end'}
                        dominantBaseline="central"
                      >
                        {porcentaje(Number(value))}
                      </text>
                    )
                  }}
                >
                  {byStatus.map((s) => (
                    <Cell
                      key={s.name}
                      fill={s.color}
                      cursor="pointer"
                      opacity={
                        filtro?.campo === 'estado' && filtro.valor !== s.estado
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
                <Tooltip
                  contentStyle={TOOLTIP_ESTILO}
                  formatter={(valor, nombre) => [
                    `${valor} (${porcentaje(Number(valor))})`,
                    nombre,
                  ]}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 grid place-items-center">
              <div className="text-center">
                <p className="text-3xl font-bold text-slate-900">
                  <NumeroFluido valor={total} formato={number} />
                </p>
                <p className="text-xs uppercase tracking-wide text-slate-500">
                  solicitudes
                </p>
              </div>
            </div>
          </>
        )}
      </div>
      {!cargando && (
        <ul className="mt-3 grid grid-cols-1 min-[420px]:grid-cols-2 gap-x-4 gap-y-2 border-t border-slate-100 pt-3 text-xs text-slate-600">
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
                  <span className="break-words">{item.name}</span>
                  <span className="ml-auto font-semibold text-slate-900">
                    {item.value}
                    <span className="ml-1 font-medium text-slate-500">
                      · {porcentaje(item.value)}
                    </span>
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </Tarjeta>
  )
}

/** Tendencia de radicadas en la ventana de seis meses, con la serie del
    periodo anterior como referencia. Click en un mes acota el panel. */
export function TendenciaSeisMeses({
  cargando,
  monthBuckets,
  filtro,
  alternarFiltro,
}: TendenciaSeisMesesProps) {
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
    <Tarjeta>
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-semibold text-slate-900">
          Tendencia · últimos 6 meses
        </h3>
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
                  <stop offset="0%" stopColor="#0052a1" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#0052a1" stopOpacity={0.02} />
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
                cursor={{ stroke: '#0052a1', strokeDasharray: '3 3' }}
              />
              {filtro?.campo === 'mes' && (
                <ReferenceLine
                  x={monthBuckets.find((b) => b.clave === filtro.valor)?.range}
                  stroke="#00468a"
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
                stroke="#0052a1"
                strokeWidth={2.5}
                fill="url(#gradSolicitudes)"
                dot={false}
                activeDot={{ r: 4, fill: '#00468a', strokeWidth: 0 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </Tarjeta>
  )
}
