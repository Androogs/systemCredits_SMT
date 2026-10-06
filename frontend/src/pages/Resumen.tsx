import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import Encabezado from '../widgets/app-shell/Encabezado'
import Tarjeta from '../shared/ui/Tarjeta'
import InsigniaEstado from '../entities/credit/ui/InsigniaEstado'
import { listApplications } from '../entities/credit/model/mockStore'
import { currency, number, dateShort } from '../shared/lib/formatters'
import {
  EMPLOYMENT_LABELS,
  type EmploymentType,
} from '../entities/credit/model/underwritingEngine'
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
  APROBADO: '#059669',          // emerald-600 - era 500, ahora más profundo
  RECHAZADO: '#BE123C',         // rose-700 - era 600, ahora vino elegante
  REQUIERE_REVISION: '#D97706', // amber-600 - era 500, ahora ámbar quemado
}

export default function Resumen() {
  const apps = useMemo(() => listApplications(), [])
  const total = apps.length
  const approved = apps.filter((a) => a.status === 'APROBADO').length
  const rejected = apps.filter((a) => a.status === 'RECHAZADO').length
  const review = apps.filter((a) => a.status === 'REQUIERE_REVISION').length

  const avgRequested = total
    ? apps.reduce((s, a) => s + a.requestedInstallment, 0) / total
    : 0
  const avgLimit = total
    ? apps.reduce((s, a) => s + a.suggestedCreditLimit, 0) / total
    : 0

  const byStatus = [
    { name: 'Aprobadas', value: approved, color: STATUS_COLORS.APROBADO },
    { name: 'Rechazadas', value: rejected, color: STATUS_COLORS.RECHAZADO },
    {
      name: 'En revisión',
      value: review,
      color: STATUS_COLORS.REQUIERE_REVISION,
    },
  ]

  const byEmployment = Object.entries(EMPLOYMENT_LABELS).map(
    ([tipo, label]) => ({
      name: label,
      value: apps.filter(
        (app) => app.employmentType === (tipo as EmploymentType),
      ).length,
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
    range: label, // ej: "abr", "may", "jun"
    count: apps.filter((a) => {
      const date = new Date(a.createdAt) // cambia a tu campo: a.date, a.fecha, etc
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
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          <Kpi
            icon={Wallet}
            label="Total solicitudes"
            value={number(total)}
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
            label="En revisión"
            value={number(review)}
            tone="amber"
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Kpi
            icon={Wallet}
            label="Ticket promedio solicitado"
            value={currency(avgRequested)}
          />
          <Kpi
            icon={Wallet}
            label="Cupo promedio sugerido"
            value={currency(avgLimit)}
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Tarjeta className="!p-0 overflow-hidden border-zinc-200 w-full max-w-[620px]">
          <div className="p-5 pb-0 flex items-center justify-between">
            <h3 className="text-[13px] font-semibold tracking-tight uppercase">Distribución por estado</h3>
            <span className="text-[11px] px-2 py-1 rounded-full bg-zinc-900 text-white">{byStatus.reduce((s, x) => s + x.value, 0)} total</span>
          </div>

          <div className="h-[260px] mt-2 relative">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={byStatus}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={65}
                  outerRadius={95}
                  paddingAngle={4}
                  stroke="none"
                  cornerRadius={6}
                >
                  {byStatus.map((s) => (
                    <Cell key={s.name} fill={s.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: '#18181b',
                    border: 'none',
                    borderRadius: 10,
                    color: '#fff',
                    fontSize: 12,
                    padding: '8px 12px'
                  }}
                  itemStyle={{ color: '#fff' }}
                />
              </PieChart>
            </ResponsiveContainer>

            <div className="absolute inset-0 grid place-items-center pointer-events-none">
              <div className="text-center">
                <p className="text-2xl font-semibold tracking-tight">{byStatus.reduce((s, x) => s + x.value, 0)}</p>
                <p className="text-[11px] uppercase tracking-wide text-zinc-500 -mt-1">Solicitudes</p>
              </div>
            </div>
          </div>

          {/* LEYENDA MÁS GRANDE */}
          <div className="grid grid-cols-3 gap-3 p-3.5 mx-3 mb-3 rounded-xl bg-zinc-50 border border-zinc-100">
            {byStatus.map((s) => (
              <div key={s.name} className="flex items-center gap-2.5">
                <span className="h-3.5 w-3.5 rounded-full shrink-0" style={{ background: s.color }} />
                <div className="min-w-0">
                  <p className="text-[12.5px] font-medium text-zinc-700 leading-none truncate">{s.name}</p>
                  <p className="text-[15px] font-bold leading-none mt-1.5">{s.value}</p>
                </div>
              </div>
            ))}
          </div>
        </Tarjeta>

          <Tarjeta>
            <h3 className="font-semibold text-slate-900 mb-4">
              Solicitudes por tipo de empleo
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
                  <th className="py-3 pr-4">ID</th>
                  <th className="py-3 pr-4">Fecha</th>
                  <th className="py-3 pr-4">Empleo</th>
                  <th className="py-3 pr-4">Score</th>
                  <th className="py-3 pr-4">Cuota</th>
                  <th className="py-3 pr-4">Cupo sugerido</th>
                  <th className="py-3 pr-4">Estado</th>
                </tr>
              </thead>
              <tbody>
                {apps.slice(0, 6).map((a) => (
                  <tr
                    key={a.id}
                    className="border-b border-slate-100 hover:bg-slate-50"
                  >
                    <td className="py-3 pr-4 font-medium">
                      <Link
                        to={`/solicitudes/${a.id}`}
                        className="text-brand-600 hover:underline"
                      >
                        {a.id}
                      </Link>
                    </td>
                    <td className="py-3 pr-4 text-slate-600">
                      {dateShort(a.createdAt)}
                    </td>
                    <td className="py-3 pr-4">
                      {EMPLOYMENT_LABELS[a.employmentType]}
                    </td>
                    <td className="py-3 pr-4">{a.creditScore}</td>
                    <td className="py-3 pr-4">
                      {currency(a.requestedInstallment)}
                    </td>
                    <td className="py-3 pr-4">
                      {currency(a.suggestedCreditLimit)}
                    </td>
                    <td className="py-3 pr-4">
                      <InsigniaEstado status={a.status} />
                    </td>
                  </tr>
                ))}
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
