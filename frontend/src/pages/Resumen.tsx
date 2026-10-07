import { Link } from 'react-router-dom'
import Encabezado from '../widgets/app-shell/Encabezado'
import Tarjeta from '../shared/ui/Tarjeta'
import InsigniaEstado from '../entities/credit/ui/InsigniaEstado'
import { currency, number, dateShort } from '../shared/lib/formatters'
import {
  estadoVisual,
  etiquetaSolicitud,
  numero,
  OCUPACION_LABELS,
  useSolicitudes,
} from '../entities/credit/model/solicitudesPanel'
import { Plus, TrendingUp, TrendingDown, Clock, Wallet } from 'lucide-react'
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts'

const STATUS_COLORS = {
  APROBADO: '#10b981',
  RECHAZADO: '#ef4444',
  REQUIERE_REVISION: '#f59e0b',
  PENDIENTE: '#94a3b8',
}

export default function Resumen() {
  const {
    datos: solicitudes,
    cargando,
    error,
  } = useSolicitudes({
    limite: 200,
  })

  const total = solicitudes.length
  const approved = solicitudes.filter(
    (s) => estadoVisual(s) === 'APROBADO',
  ).length
  const rejected = solicitudes.filter(
    (s) => estadoVisual(s) === 'RECHAZADO',
  ).length
  const pendientes = solicitudes.filter(
    (s) => estadoVisual(s) === 'PENDIENTE',
  ).length
  const review = total - approved - rejected - pendientes

  const cupos = solicitudes
    .filter((s) => estadoVisual(s) === 'APROBADO')
    .map((s) => numero(s.evaluacion?.cupo_sugerido))
    .filter((n): n is number => n != null)
  const capacidades = solicitudes
    .map((s) => numero(s.evaluacion?.capacidad_pago))
    .filter((n): n is number => n != null)
  const avgLimit = cupos.length
    ? cupos.reduce((a, b) => a + b, 0) / cupos.length
    : 0
  const avgCapacidad = capacidades.length
    ? capacidades.reduce((a, b) => a + b, 0) / capacidades.length
    : 0

  const byStatus = [
    { name: 'Aprobadas', value: approved, color: STATUS_COLORS.APROBADO },
    { name: 'Rechazadas', value: rejected, color: STATUS_COLORS.RECHAZADO },
    {
      name: 'En revisión',
      value: review,
      color: STATUS_COLORS.REQUIERE_REVISION,
    },
    {
      name: 'Pendientes de evaluación',
      value: pendientes,
      color: STATUS_COLORS.PENDIENTE,
    },
  ]

  const byEmployment = Object.entries(OCUPACION_LABELS).map(
    ([tipo, label]) => ({
      name: label,
      value: solicitudes.filter((s) => s.ocupacion === tipo).length,
    }),
  )

  const last6Months = [...Array(6)].map((_, i) => {
    const d = new Date()
    d.setMonth(d.getMonth() - (5 - i))
    return {
      month: d.getMonth(),
      year: d.getFullYear(),
      label: d.toLocaleString('es-CO', { month: 'short' }),
    }
  })

  const monthBuckets = last6Months.map(({ month, year, label }) => ({
    range: label,
    count: solicitudes.filter((s) => {
      const date = new Date(s.fecha_hora)
      return date.getMonth() === month && date.getFullYear() === year
    }).length,
  }))

  return (
    <>
      <Encabezado
        title="Resumen"
        subtitle="Resumen general de solicitudes y decisiones"
        actions={
          <Link to="/solicitudes" className="btn-primary">
            <Plus size={16} /> Solicitudes
          </Link>
        }
      />
      <div className="p-6 space-y-6 overflow-auto">
        {error && (
          <Tarjeta className="border-red-200 bg-red-50/40 text-sm text-red-800">
            No se pudo cargar el resumen: {error}
          </Tarjeta>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          <Kpi
            icon={Wallet}
            label="Total solicitudes"
            value={cargando ? '…' : number(total)}
            tone="brand"
          />
          <Kpi
            icon={TrendingUp}
            label="Tasa de aprobación"
            value={`${total ? ((approved / total) * 100).toFixed(1) : 0}%`}
            tone="emerald"
          />
          <Kpi
            icon={TrendingDown}
            label="Tasa de rechazo"
            value={`${total ? ((rejected / total) * 100).toFixed(1) : 0}%`}
            tone="red"
          />
          <Kpi
            icon={Clock}
            label="En revisión / pendiente"
            value={number(review)}
            tone="amber"
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Kpi
            icon={Wallet}
            label="Capacidad de pago promedio"
            value={currency(avgCapacidad)}
          />
          <Kpi
            icon={Wallet}
            label="Cupo promedio aprobado"
            value={currency(avgLimit)}
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Tarjeta>
            <h3 className="font-semibold text-slate-900 mb-4">
              Distribución por estado
            </h3>
            <div className="h-64">
              <ResponsiveContainer>
                <PieChart>
                  <Pie
                    data={byStatus}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={60}
                    outerRadius={90}
                    paddingAngle={3}
                  >
                    {byStatus.map((s) => (
                      <Cell key={s.name} fill={s.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </Tarjeta>

          <Tarjeta>
            <h3 className="font-semibold text-slate-900 mb-4">
              Solicitudes por ocupación
            </h3>
            <div className="h-64">
              <ResponsiveContainer>
                <BarChart data={byEmployment}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Bar dataKey="value" fill="#099dd7" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Tarjeta>

          <Tarjeta className="lg:col-span-2">
            <h3 className="font-semibold text-slate-900 mb-4">
              Últimos 6 meses
            </h3>
            <div className="h-64">
              <ResponsiveContainer>
                <BarChart data={monthBuckets}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="range" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#065f83" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Tarjeta>
        </div>

        <Tarjeta>
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-slate-900">
              Últimas solicitudes
            </h3>
            <Link
              to="/solicitudes"
              className="text-sm font-medium text-brand-600 hover:text-brand-700"
            >
              Ver todas →
            </Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-slate-500 border-b border-slate-200">
                  <th className="py-3 pr-4">N°</th>
                  <th className="py-3 pr-4">Solicitante</th>
                  <th className="py-3 pr-4">Fecha</th>
                  <th className="py-3 pr-4">Ocupación</th>
                  <th className="py-3 pr-4">Score</th>
                  <th className="py-3 pr-4">Cupo sugerido</th>
                  <th className="py-3 pr-4">Estado</th>
                </tr>
              </thead>
              <tbody>
                {solicitudes.slice(0, 6).map((s) => {
                  const cupo = numero(s.evaluacion?.cupo_sugerido)
                  return (
                    <tr
                      key={s.id_solicitud}
                      className="border-b border-slate-100 hover:bg-slate-50"
                    >
                      <td className="py-3 pr-4 font-medium">
                        <Link
                          to={`/solicitudes/${s.id_solicitud}`}
                          className="text-brand-600 hover:underline"
                        >
                          {etiquetaSolicitud(s)}
                        </Link>
                      </td>
                      <td className="py-3 pr-4 whitespace-nowrap">
                        {s.nombre_cliente}
                      </td>
                      <td className="py-3 pr-4 text-slate-600">
                        {dateShort(s.fecha_hora)}
                      </td>
                      <td className="py-3 pr-4">
                        {s.ocupacion
                          ? (OCUPACION_LABELS[s.ocupacion] ?? s.ocupacion)
                          : '—'}
                      </td>
                      <td className="py-3 pr-4">
                        {s.evaluacion?.score != null
                          ? Number(s.evaluacion.score)
                          : '—'}
                      </td>
                      <td className="py-3 pr-4">
                        {cupo != null && estadoVisual(s) === 'APROBADO'
                          ? currency(cupo)
                          : '—'}
                      </td>
                      <td className="py-3 pr-4">
                        <InsigniaEstado status={estadoVisual(s)} />
                      </td>
                    </tr>
                  )
                })}
                {!cargando && solicitudes.length === 0 && !error && (
                  <tr>
                    <td
                      colSpan={7}
                      className="py-10 text-center text-slate-500"
                    >
                      Aún no hay solicitudes registradas.
                    </td>
                  </tr>
                )}
                {cargando && (
                  <tr>
                    <td
                      colSpan={7}
                      className="py-10 text-center text-slate-500"
                    >
                      Cargando solicitudes…
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Tarjeta>
      </div>
    </>
  )
}

function Kpi({
  icon: Icon,
  label,
  value,
  tone = 'brand',
}: {
  icon: typeof Wallet
  label: string
  value: string
  tone?: 'brand' | 'emerald' | 'red' | 'amber'
}) {
  const tones = {
    brand: 'bg-brand-50 text-brand-600',
    emerald: 'bg-emerald-50 text-emerald-600',
    red: 'bg-red-50 text-red-600',
    amber: 'bg-amber-50 text-amber-600',
  }
  return (
    <Tarjeta className="flex items-center gap-4">
      <div
        className={`h-11 w-11 rounded-xl grid place-items-center ${tones[tone]}`}
      >
        <Icon size={20} />
      </div>
      <div className="min-w-0">
        <p className="text-xs uppercase tracking-wide text-slate-500">
          {label}
        </p>
        <p className="text-xl font-bold text-slate-900 truncate">{value}</p>
      </div>
    </Tarjeta>
  )
}
