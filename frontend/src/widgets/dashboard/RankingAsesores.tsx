import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { number } from '../../shared/lib/formatters'
import { useEsMovil } from '../../shared/lib/useEsMovil'
import type { EmbudoAsesorApi } from '../../features/credit-origination/api/originacionApi'

const TOOLTIP_ESTILO = {
  borderRadius: 12,
  border: '1px solid #e2e8f0',
  boxShadow: '0 4px 12px rgba(15,23,42,0.10)',
  fontSize: 12,
  padding: '8px 12px',
} as const

const TICK_ESTILO = { fontSize: 11, fill: '#64748b' } as const

/** Cuántas personas muestra el ranking; el resto queda en la tabla
    colapsable que acompaña a la gráfica. */
const TOP_N = 12
const ALTO_GRAFICA = 240

interface PuntoAsesor {
  nombre: string
  nombreCorto: string
  cedula: string | null
  titularAnterior: boolean
  aprobadas: number
  otras: number
  radicadas: number
}

function aPunto(fila: EmbudoAsesorApi): PuntoAsesor {
  const nombre =
    fila.asesor.length > 14 ? `${fila.asesor.slice(0, 13)}…` : fila.asesor
  return {
    nombre: fila.asesor,
    nombreCorto: nombre,
    cedula: fila.cedula,
    titularAnterior: fila.titular_anterior,
    aprobadas: fila.aprobadas,
    otras: Math.max(fila.radicadas - fila.aprobadas, 0),
    radicadas: fila.radicadas,
  }
}

function ContenidoTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: { payload: PuntoAsesor }[]
}) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div style={TOOLTIP_ESTILO}>
      <p className="font-semibold text-slate-900">
        {p.nombre}
        {p.cedula ? ` · CC ${p.cedula}` : ''}
      </p>
      <p className="text-slate-600">Radicadas: {number(p.radicadas)}</p>
      <p className="text-slate-600">
        Aprobadas: {number(p.aprobadas)} (
        {p.radicadas > 0 ? Math.round((p.aprobadas / p.radicadas) * 100) : 0}
        %)
      </p>
    </div>
  )
}

/** Ranking horizontal de producción por asesor (por PERSONA, no por
    cuenta): top N por radicadas con la composición aprobadas / resto.
    Recharts se carga en chunk aparte. */
export default function RankingAsesores({
  asesores,
  top = TOP_N,
}: {
  asesores: EmbudoAsesorApi[]
  top?: number
}) {
  const esMovil = useEsMovil()
  const datos = asesores.slice(0, top).map(aPunto)
  const restantes = asesores.length - datos.length
  const ariaTop = datos
    .slice(0, 5)
    .map((d) => `${d.nombre}: ${d.radicadas}`)
    .join(', ')
  return (
    <div>
      {/* Leyenda honesta: los dos segmentos suman radicadas. */}
      <div className="mb-3 flex items-center gap-3 text-[11px] text-slate-500">
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm bg-[#2b7fff]" />
          Aprobadas
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm bg-[#8ec5ff]" />
          Otras
        </span>
      </div>
      <div
        role="img"
        aria-label={`Ranking de asesores por solicitudes radicadas. Principales: ${ariaTop}`}
        style={{ height: ALTO_GRAFICA }}
      >
        <ResponsiveContainer>
          <BarChart
            data={datos}
            margin={{ top: 8, right: 8, bottom: 0, left: 0 }}
            barCategoryGap="25%"
          >
            <XAxis
              dataKey="nombreCorto"
              tick={TICK_ESTILO}
              tickLine={false}
              axisLine={{ stroke: '#cbd5e1' }}
              interval={0}
              angle={esMovil ? -35 : 0}
              textAnchor={esMovil ? 'end' : 'middle'}
              height={esMovil ? 56 : 30}
            />
            <YAxis
              tick={TICK_ESTILO}
              tickLine={false}
              axisLine={false}
              allowDecimals={false}
              width={32}
            />
            <Tooltip
              content={<ContenidoTooltip />}
              cursor={{ fill: 'rgba(43,127,255,0.06)' }}
            />
            <Bar
              dataKey="aprobadas"
              name="Aprobadas"
              stackId="a"
              fill="#2b7fff"
              maxBarSize={56}
            >
              {datos.map((d, i) => (
                <Cell
                  key={d.cedula ?? `${d.nombre}-${i}`}
                  opacity={d.titularAnterior ? 0.45 : 1}
                />
              ))}
            </Bar>
            <Bar
              dataKey="otras"
              name="Otras"
              stackId="a"
              fill="#8ec5ff"
              radius={[4, 4, 0, 0]}
              maxBarSize={56}
            >
              {datos.map((d, i) => (
                <Cell
                  key={d.cedula ?? `${d.nombre}-${i}`}
                  opacity={d.titularAnterior ? 0.45 : 1}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-1 text-[11px] text-slate-400">
        {asesores.length} {asesores.length === 1 ? 'persona' : 'personas'} con
        producción
        {restantes > 0
          ? ` — la gráfica muestra el top ${top}, el resto está en la tabla`
          : ' en el periodo'}
        .
      </p>
    </div>
  )
}
