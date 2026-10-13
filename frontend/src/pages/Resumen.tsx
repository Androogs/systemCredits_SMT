import { useState } from 'react'
import { Link } from 'react-router-dom'
import Encabezado from '../widgets/app-shell/Encabezado'
import Tarjeta from '../shared/ui/Tarjeta'
import Skeleton, { FilasSkeleton } from '../shared/ui/Skeleton'
import InsigniaEstado from '../entities/credit/ui/InsigniaEstado'
import { currency, number, dateShort } from '../shared/lib/formatters'
import { useCuentaAscendente } from '../shared/lib/useCuentaAscendente'
import { useRol } from '../shared/lib/sesion'
import {
  estadoParaVista,
  etiquetaSolicitud,
  numero,
  OCUPACION_LABELS,
  useSolicitudes,
} from '../entities/credit/model/solicitudesPanel'
import { Plus, X } from 'lucide-react'
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
  AreaChart,
  Area,
  LabelList,
  ReferenceLine,
} from 'recharts'

const STATUS_COLORS = {
  APROBADO: '#10b981',
  RECHAZADO: '#ef4444',
  REQUIERE_REVISION: '#f59e0b',
  PENDIENTE: '#94a3b8',
}

const TOOLTIP_ESTILO = {
  borderRadius: 12,
  border: '1px solid #e2e8f0',
  boxShadow: '0 4px 12px rgba(15,23,42,0.10)',
  fontSize: 12,
  padding: '8px 12px',
} as const

const TICK_ESTILO = { fontSize: 12, fill: '#64748b' } as const

interface FiltroPanel {
  campo: 'estado' | 'ocupacion' | 'mes'
  valor: string
  etiqueta: string
}

/** Saludo según la hora local (estilo portal del asesor). */
function saludoDelDia(): string {
  const h = new Date().getHours()
  if (h < 12) return 'Buenos días'
  if (h < 19) return 'Buenas tardes'
  return 'Buenas noches'
}

export default function Resumen() {
  const {
    datos: solicitudes,
    cargando,
    error,
  } = useSolicitudes({
    limite: 200,
  })
  const rol = useRol()
  const esAsesor = rol === 'asesor'
  const [filtro, setFiltro] = useState<FiltroPanel | null>(null)
  const alternarFiltro = (f: FiltroPanel) =>
    setFiltro((actual) =>
      actual && actual.campo === f.campo && actual.valor === f.valor ? null : f,
    )

  // Con filtro de mes activo, KPIs y gráficas recalculan sobre ese mes;
  // el gráfico "Últimos 6 meses" conserva todos los datos como selector.
  const base =
    filtro?.campo === 'mes'
      ? solicitudes.filter((s) => {
          const d = new Date(s.fecha_hora)
          return `${d.getFullYear()}-${d.getMonth()}` === filtro.valor
        })
      : solicitudes

  const total = base.length
  const approved = base.filter(
    (s) => estadoParaVista(s, esAsesor) === 'APROBADO',
  ).length
  const rejected = base.filter(
    (s) => estadoParaVista(s, esAsesor) === 'RECHAZADO',
  ).length
  const pendientes = base.filter(
    (s) => estadoParaVista(s, esAsesor) === 'PENDIENTE',
  ).length
  const review = total - approved - rejected - pendientes

  const cupos = base
    .filter((s) => estadoParaVista(s, esAsesor) === 'APROBADO')
    .map((s) => numero(s.evaluacion?.cupo_sugerido))
    .filter((n): n is number => n != null)
  const capacidades = base
    .map((s) => numero(s.evaluacion?.capacidad_pago))
    .filter((n): n is number => n != null)
  const avgLimit = cupos.length
    ? cupos.reduce((a, b) => a + b, 0) / cupos.length
    : 0
  const avgCapacidad = capacidades.length
    ? capacidades.reduce((a, b) => a + b, 0) / capacidades.length
    : 0
  const sumaCupos = cupos.reduce((a, b) => a + b, 0)

  // Cartera: solicitudes que ya llegaron a desembolso.
  const colocadas = base.filter((s) => s.estado === 'desembolsada')
  const cupoColocado = colocadas.reduce(
    (acc, s) => acc + (numero(s.evaluacion?.cupo_sugerido) ?? 0),
    0,
  )

  const byStatus = [
    {
      estado: 'APROBADO',
      name: 'Aprobadas',
      value: approved,
      color: STATUS_COLORS.APROBADO,
    },
    {
      estado: 'RECHAZADO',
      name: 'Rechazadas',
      value: rejected,
      color: STATUS_COLORS.RECHAZADO,
    },
    {
      estado: 'REQUIERE_REVISION',
      name: 'En revisión',
      value: review,
      color: STATUS_COLORS.REQUIERE_REVISION,
    },
    {
      estado: 'PENDIENTE',
      name: 'Pendientes de evaluación',
      value: pendientes,
      color: STATUS_COLORS.PENDIENTE,
    },
  ].filter((item) => !(esAsesor && item.estado === 'REQUIERE_REVISION'))

  const byEmployment = Object.entries(OCUPACION_LABELS).map(
    ([tipo, label]) => ({
      tipo,
      name: label,
      value: base.filter((s) => s.ocupacion === tipo).length,
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
    clave: `${year}-${month}`,
    count: solicitudes.filter((s) => {
      const date = new Date(s.fecha_hora)
      return date.getMonth() === month && date.getFullYear() === year
    }).length,
  }))

  const porOcupacion = Object.entries(OCUPACION_LABELS)
    .map(([tipo, label]) => {
      const grupo = base.filter((s) => s.ocupacion === tipo)
      const aprobadas = grupo.filter(
        (s) => estadoParaVista(s, esAsesor) === 'APROBADO',
      ).length
      const rechazadas = grupo.filter(
        (s) => estadoParaVista(s, esAsesor) === 'RECHAZADO',
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

  // Animación 0 → valor real en KPIs y centro de la dona
  const totalAnimado = useCuentaAscendente(total)

  const solicitudesFiltradas =
    filtro == null
      ? solicitudes
      : solicitudes.filter((s) => {
          if (filtro.campo === 'estado')
            return estadoParaVista(s, esAsesor) === filtro.valor
          if (filtro.campo === 'ocupacion') return s.ocupacion === filtro.valor
          const d = new Date(s.fecha_hora)
          return `${d.getFullYear()}-${d.getMonth()}` === filtro.valor
        })

  return (
    <>
      <Encabezado
        title={saludoDelDia()}
        subtitle={
          esAsesor
            ? 'Prioridades comerciales y solicitudes asignadas'
            : 'Resumen general de solicitudes y decisiones'
        }
        actions={
          <Link to="/solicitudes" className="btn-primary">
            <Plus size={16} /> Solicitudes
          </Link>
        }
      />
      <div className="p-6 space-y-6 overflow-auto">
        {error && (
          <Tarjeta className="border-red-200 bg-red-50/40 text-sm text-red-800">
            <p role="alert">No se pudo cargar el resumen: {error}</p>
          </Tarjeta>
        )}
        {filtro?.campo === 'mes' && (
          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-brand-200 bg-brand-50/60 px-4 py-2.5 text-sm text-brand-800">
            <span>
              Mostrando <strong>{filtro.etiqueta.toLowerCase()}</strong> — KPIs,
              distribución, ocupación y tabla recalculan sobre este mes.
            </span>
            <button
              type="button"
              onClick={() => setFiltro(null)}
              className="inline-flex items-center gap-1 rounded-full bg-white/80 px-2.5 py-0.5 text-xs font-semibold text-brand-700 ring-1 ring-brand-500/30 hover:bg-white"
            >
              <X size={12} /> Ver todos los meses
            </button>
          </div>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          <Kpi
            label="Solicitudes activas"
            valor={total}
            detalle={`${review + pendientes} requieren gestión`}
            tone="brand"
            cargando={cargando}
          />
          <Kpi
            label="Aprobadas"
            valor={approved}
            detalle={`Conversión ${total ? Math.round((approved / total) * 100) : 0}%`}
            tone="emerald"
            cargando={cargando}
          />
          <Kpi
            label="Monto aprobado"
            valor={sumaCupos}
            formato={(n) => currency(Math.round(n))}
            detalle={`Promedio ${currency(avgLimit)}`}
            tone="brand"
            cargando={cargando}
          />
          <Kpi
            label="Requieren gestión"
            valor={review + pendientes}
            detalle={
              esAsesor
                ? `${pendientes} por gestionar`
                : `${review} en comité · ${pendientes} sin evaluar`
            }
            tone="red"
            cargando={cargando}
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          <Kpi
            label="Créditos colocados"
            valor={colocadas.length}
            detalle="Desembolso confirmado"
            tone="emerald"
            cargando={cargando}
          />
          <Kpi
            label="Cupo total colocado"
            valor={cupoColocado}
            formato={(n) => currency(Math.round(n))}
            detalle={`${colocadas.length} operaciones`}
            tone="emerald"
            cargando={cargando}
          />
          <Kpi
            label="Tasa de rechazo"
            valor={total ? (rejected / total) * 100 : 0}
            formato={(n) => `${n.toFixed(1)}%`}
            detalle={`${rejected} rechazadas`}
            tone="red"
            cargando={cargando}
          />
          <Kpi
            label="Capacidad de pago promedio"
            valor={avgCapacidad}
            formato={(n) => currency(Math.round(n))}
            detalle={`Sobre ${capacidades.length} evaluadas`}
            tone="brand"
            cargando={cargando}
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Tarjeta>
            <h3 className="font-semibold text-slate-900 mb-4">
              Distribución por estado
            </h3>
            <div
              className="relative h-56"
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
              <ul className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-xs text-slate-600">
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

          <Tarjeta>
            <h3 className="font-semibold text-slate-900 mb-4">
              Solicitudes por ocupación
            </h3>
            <div
              className="h-64"
              aria-busy={cargando}
              role="img"
              aria-label={`Solicitudes por ocupación: ${byEmployment.map((item) => `${item.name}: ${item.value}`).join(', ')}`}
            >
              {cargando ? (
                <Skeleton className="h-full w-full rounded-xl" />
              ) : (
                <ResponsiveContainer>
                  <BarChart
                    data={byEmployment}
                    margin={{ top: 20, right: 8, bottom: 0, left: -18 }}
                    onClick={(estado) => {
                      const p = estado?.activePayload?.[0]?.payload as
                        { tipo?: string; name?: string } | undefined
                      if (p?.tipo)
                        alternarFiltro({
                          campo: 'ocupacion',
                          valor: p.tipo,
                          etiqueta: p.name ?? p.tipo,
                        })
                    }}
                    className="cursor-pointer"
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="#e2e8f0"
                      vertical={false}
                    />
                    <XAxis
                      dataKey="name"
                      tick={TICK_ESTILO}
                      tickLine={false}
                      axisLine={{ stroke: '#cbd5e1' }}
                    />
                    <YAxis
                      tick={TICK_ESTILO}
                      tickLine={false}
                      axisLine={false}
                      allowDecimals={false}
                    />
                    <Tooltip
                      contentStyle={TOOLTIP_ESTILO}
                      cursor={{ fill: 'rgba(9,157,215,0.06)' }}
                    />
                    <Bar dataKey="value" radius={[8, 8, 0, 0]}>
                      {byEmployment.map((e) => (
                        <Cell
                          key={e.tipo}
                          fill="#099dd7"
                          opacity={
                            filtro?.campo === 'ocupacion' &&
                            filtro.valor !== e.tipo
                              ? 0.3
                              : 1
                          }
                        />
                      ))}
                      <LabelList
                        dataKey="value"
                        position="top"
                        style={{
                          fontSize: 12,
                          fill: '#475569',
                          fontWeight: 600,
                        }}
                      />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </Tarjeta>

          <Tarjeta className="lg:col-span-2">
            <h3 className="font-semibold text-slate-900 mb-4">
              Últimos 6 meses
            </h3>
            <div
              className="h-64"
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
                    margin={{ top: 12, right: 16, bottom: 0, left: -18 }}
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
                        <stop
                          offset="0%"
                          stopColor="#099dd7"
                          stopOpacity={0.35}
                        />
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
                      tick={TICK_ESTILO}
                      tickLine={false}
                      axisLine={{ stroke: '#cbd5e1' }}
                    />
                    <YAxis
                      tick={TICK_ESTILO}
                      tickLine={false}
                      axisLine={false}
                      allowDecimals={false}
                    />
                    <Tooltip
                      contentStyle={TOOLTIP_ESTILO}
                      cursor={{ stroke: '#099dd7', strokeDasharray: '3 3' }}
                    />
                    {filtro?.campo === 'mes' && (
                      <ReferenceLine
                        x={
                          monthBuckets.find((b) => b.clave === filtro.valor)
                            ?.range
                        }
                        stroke="#087ead"
                        strokeWidth={2}
                        strokeDasharray="4 3"
                      />
                    )}
                    <Area
                      type="monotone"
                      dataKey="count"
                      name="Solicitudes"
                      stroke="#099dd7"
                      strokeWidth={2.5}
                      fill="url(#gradSolicitudes)"
                      dot={{ r: 3.5, fill: '#099dd7', strokeWidth: 0 }}
                      activeDot={{ r: 5, fill: '#087ead', strokeWidth: 0 }}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          </Tarjeta>

          <Tarjeta className="lg:col-span-2">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
              <h3 className="font-semibold text-slate-900">
                Aprobación por ocupación
              </h3>
              <div className="flex gap-3 text-xs text-slate-600">
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                  Aprobadas
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-red-500" />
                  Rechazadas
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-slate-300" />
                  Otras
                </span>
              </div>
            </div>
            <div
              className="space-y-3"
              aria-busy={cargando}
              role="img"
              aria-label={`Aprobación por ocupación: ${porOcupacion.map((g) => `${g.label}: ${g.aprobadas} aprobadas de ${g.total}`).join(', ')}`}
            >
              {cargando ? (
                <div className="space-y-3" aria-hidden="true">
                  {[100, 85, 70].map((w) => (
                    <div
                      key={w}
                      className="h-9 animate-pulse rounded-lg bg-slate-200"
                      style={{ width: `${w}%` }}
                    />
                  ))}
                </div>
              ) : porOcupacion.length === 0 ? (
                <p className="py-10 text-center text-sm text-slate-500">
                  Aún no hay solicitudes registradas.
                </p>
              ) : (
                porOcupacion.map((g) => {
                  const tasa = Math.round((g.aprobadas / g.total) * 100)
                  const activo =
                    filtro?.campo === 'ocupacion' && filtro.valor === g.tipo
                  return (
                    <button
                      key={g.tipo}
                      type="button"
                      onClick={() =>
                        alternarFiltro({
                          campo: 'ocupacion',
                          valor: g.tipo,
                          etiqueta: g.label,
                        })
                      }
                      aria-pressed={activo}
                      className={`flex w-full items-center gap-3 rounded-lg px-1.5 py-1 text-sm transition hover:bg-slate-50 ${
                        activo ? 'bg-slate-100 ring-1 ring-slate-300' : ''
                      } ${
                        filtro?.campo === 'ocupacion' && !activo
                          ? 'opacity-40'
                          : ''
                      }`}
                    >
                      <span className="w-28 shrink-0 text-left text-slate-600">
                        {g.label}
                      </span>
                      <span className="flex h-9 min-w-0 flex-1 overflow-hidden rounded-lg bg-slate-100">
                        {g.aprobadas > 0 && (
                          <span
                            className="flex h-full items-center justify-center bg-emerald-500 px-2 text-xs font-semibold text-white"
                            style={{
                              width: `${(g.aprobadas / g.total) * 100}%`,
                            }}
                          >
                            {g.aprobadas}
                          </span>
                        )}
                        {g.rechazadas > 0 && (
                          <span
                            className="flex h-full items-center justify-center bg-red-400 px-2 text-xs font-semibold text-white"
                            style={{
                              width: `${(g.rechazadas / g.total) * 100}%`,
                            }}
                          >
                            {g.rechazadas}
                          </span>
                        )}
                        {g.otras > 0 && (
                          <span
                            className="flex h-full items-center justify-center bg-slate-300 px-2 text-xs font-semibold text-slate-600"
                            style={{ width: `${(g.otras / g.total) * 100}%` }}
                          >
                            {g.otras}
                          </span>
                        )}
                      </span>
                      <span className="w-24 shrink-0 text-right text-xs text-slate-500">
                        {g.total} · {tasa}% apr.
                      </span>
                    </button>
                  )
                })
              )}
            </div>
          </Tarjeta>
        </div>

        <Tarjeta>
          <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
            <div className="flex items-center gap-3">
              <h3 className="font-semibold text-slate-900">
                Últimas solicitudes
              </h3>
              {filtro && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-50 px-3 py-1 text-xs font-medium text-brand-700 ring-1 ring-brand-500/30">
                  {filtro.etiqueta}: {solicitudesFiltradas.length}
                  <button
                    type="button"
                    onClick={() => setFiltro(null)}
                    className="rounded-full p-0.5 hover:bg-brand-100"
                    aria-label="Quitar filtro"
                  >
                    <X size={12} />
                  </button>
                </span>
              )}
            </div>
            <Link
              to="/solicitudes"
              className="text-sm font-medium text-brand-600 hover:text-brand-700"
            >
              Ver todas →
            </Link>
          </div>
          <div
            className="overflow-x-auto"
            role="region"
            aria-label="Tabla de últimas solicitudes"
            tabIndex={0}
          >
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-slate-500 border-b border-slate-200">
                  <th scope="col" className="py-3 pr-4">
                    N°
                  </th>
                  <th scope="col" className="py-3 pr-4">
                    Solicitante
                  </th>
                  <th scope="col" className="py-3 pr-4">
                    Fecha
                  </th>
                  <th scope="col" className="py-3 pr-4">
                    Ocupación
                  </th>
                  {!esAsesor && (
                    <th scope="col" className="py-3 pr-4">
                      Score
                    </th>
                  )}
                  <th scope="col" className="py-3 pr-4">
                    Cupo sugerido
                  </th>
                  <th scope="col" className="py-3 pr-4">
                    Estado
                  </th>
                </tr>
              </thead>
              <tbody aria-busy={cargando}>
                {solicitudesFiltradas.slice(0, filtro ? 15 : 6).map((s) => {
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
                      {!esAsesor && (
                        <td className="py-3 pr-4">
                          {s.evaluacion?.score != null
                            ? Number(s.evaluacion.score)
                            : '—'}
                        </td>
                      )}
                      <td className="py-3 pr-4">
                        {cupo != null &&
                        estadoParaVista(s, esAsesor) === 'APROBADO'
                          ? currency(cupo)
                          : '—'}
                      </td>
                      <td className="py-3 pr-4">
                        <InsigniaEstado status={estadoParaVista(s, esAsesor)} />
                      </td>
                    </tr>
                  )
                })}
                {!cargando && solicitudesFiltradas.length === 0 && !error && (
                  <tr>
                    <td
                      colSpan={esAsesor ? 6 : 7}
                      className="py-10 text-center text-slate-500"
                    >
                      {filtro
                        ? 'Ninguna solicitud coincide con el filtro.'
                        : 'Aún no hay solicitudes registradas.'}
                    </td>
                  </tr>
                )}
                {cargando && (
                  <FilasSkeleton filas={4} columnas={esAsesor ? 6 : 7} />
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
  label,
  valor,
  formato = (n) => number(Math.round(n)),
  detalle,
  tone = 'brand',
  cargando = false,
}: {
  label: string
  valor: number
  formato?: (n: number) => string
  detalle?: string
  tone?: 'brand' | 'emerald' | 'red' | 'amber'
  cargando?: boolean
}) {
  const animado = useCuentaAscendente(valor)
  const dots = {
    brand: 'bg-brand-500',
    emerald: 'bg-emerald-500',
    red: 'bg-red-500',
    amber: 'bg-amber-500',
  }
  const detalleTones = {
    brand: 'text-brand-600',
    emerald: 'text-emerald-600',
    red: 'text-red-600',
    amber: 'text-amber-600',
  }
  return (
    <Tarjeta className="relative">
      <span
        className={`absolute right-4 top-4 h-2 w-2 rounded-full ${dots[tone]}`}
        aria-hidden="true"
      />
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <div className="min-w-0" aria-busy={cargando}>
        {cargando ? (
          <Skeleton className="mt-2 h-7 w-24" />
        ) : (
          <p className="mt-1.5 text-2xl font-bold text-slate-900 truncate">
            {formato(animado)}
          </p>
        )}
      </div>
      {detalle && (
        <p className={`mt-1 text-xs font-semibold ${detalleTones[tone]}`}>
          {detalle}
        </p>
      )}
    </Tarjeta>
  )
}
