import { Link } from 'react-router-dom'
import Encabezado from '../widgets/app-shell/Encabezado'
import Tarjeta from '../shared/ui/Tarjeta'
import InsigniaEstado from '../entities/credit/ui/InsigniaEstado'
import {
  estadoVisual,
  etiquetaSolicitud,
  numero,
  useSolicitudes,
} from '../entities/credit/model/solicitudesPanel'
import { currency, dateShort, number } from '../shared/lib/formatters'
import {
  FilePlus2,
  Calculator,
  ClipboardList,
  Inbox,
  TrendingUp,
  CheckCircle2,
  Clock,
  ArrowRight,
} from 'lucide-react'

export default function PanelAsesor() {
  const {
    datos: solicitudes,
    cargando,
    error,
  } = useSolicitudes({
    limite: 200,
  })

  const aprobadas = solicitudes.filter(
    (s) => estadoVisual(s) === 'APROBADO',
  ).length
  const enCola = solicitudes.filter((s) => {
    const v = estadoVisual(s)
    return v === 'REQUIERE_REVISION' || v === 'PENDIENTE'
  })
  const cola = [
    ...enCola.filter((s) => estadoVisual(s) === 'PENDIENTE'),
    ...enCola.filter((s) => estadoVisual(s) === 'REQUIERE_REVISION'),
    ...solicitudes.filter((s) => !enCola.includes(s)),
  ].slice(0, 8)

  return (
    <>
      <Encabezado
        title="Panel del asesor"
        subtitle="Tu cola de trabajo y gestión del día"
      />
      <div className="p-6 space-y-6 overflow-auto">
        {error && (
          <Tarjeta className="border-red-200 bg-red-50/40 text-sm text-red-800">
            No se pudo cargar la cola de trabajo: {error}
          </Tarjeta>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          <Kpi
            icon={Inbox}
            label="Solicitudes"
            value={cargando ? '…' : number(solicitudes.length)}
            tone="brand"
          />
          <Kpi
            icon={CheckCircle2}
            label="Aprobadas"
            value={number(aprobadas)}
            tone="emerald"
          />
          <Kpi
            icon={Clock}
            label="En revisión / pendientes"
            value={number(enCola.length)}
            tone="amber"
          />
          <Kpi
            icon={TrendingUp}
            label="Tasa de aprobación"
            value={`${solicitudes.length ? ((aprobadas / solicitudes.length) * 100).toFixed(0) : 0}%`}
            tone="emerald"
          />
        </div>

        <Tarjeta>
          <h3 className="font-semibold text-slate-900 mb-4">
            Acciones rápidas
          </h3>
          <div className="grid sm:grid-cols-3 gap-3">
            <Accion
              to="/nueva-solicitud"
              icon={FilePlus2}
              titulo="Nueva solicitud"
              detalle="Flujo guiado de originación"
            />
            <Accion
              to="/simulador"
              icon={Calculator}
              titulo="Simulador"
              detalle="Cuotas, tasas y plazos"
            />
            <Accion
              to="/solicitudes"
              icon={ClipboardList}
              titulo="Solicitudes"
              detalle="Historial y filtros"
            />
          </div>
        </Tarjeta>

        <Tarjeta className="p-0">
          <div className="flex items-center justify-between px-5 pt-5 pb-3">
            <h3 className="font-semibold text-slate-900">Cola de trabajo</h3>
            <Link
              to="/solicitudes"
              className="text-sm font-medium text-brand-600 hover:text-brand-700 inline-flex items-center gap-1"
            >
              Ver todas <ArrowRight size={14} />
            </Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-slate-500 border-b border-slate-200">
                  <th className="px-5 py-3">N°</th>
                  <th className="px-5 py-3">Cliente</th>
                  <th className="px-5 py-3">Destino</th>
                  <th className="px-5 py-3">Fecha</th>
                  <th className="px-5 py-3">Cupo sugerido</th>
                  <th className="px-5 py-3">Estado</th>
                </tr>
              </thead>
              <tbody>
                {cola.map((s) => {
                  const visual = estadoVisual(s)
                  const cupo = numero(s.evaluacion?.cupo_sugerido)
                  return (
                    <tr
                      key={s.id_solicitud}
                      className="border-b border-slate-100 hover:bg-slate-50"
                    >
                      <td className="px-5 py-3 font-medium">
                        <Link
                          to={`/solicitudes/${s.id_solicitud}`}
                          className="text-brand-600 hover:underline"
                        >
                          {etiquetaSolicitud(s)}
                        </Link>
                      </td>
                      <td className="px-5 py-3 whitespace-nowrap">
                        {s.nombre_cliente}
                      </td>
                      <td className="px-5 py-3 whitespace-nowrap text-slate-600">
                        {s.destino_credito ?? '—'}
                      </td>
                      <td className="px-5 py-3 text-slate-600 whitespace-nowrap">
                        {dateShort(s.fecha_hora)}
                      </td>
                      <td className="px-5 py-3">
                        {cupo != null && visual === 'APROBADO'
                          ? currency(cupo)
                          : '—'}
                      </td>
                      <td className="px-5 py-3">
                        <span className="inline-flex items-center gap-2">
                          <InsigniaEstado status={visual} />
                          <span className="text-xs text-slate-600 capitalize">
                            {s.decision
                              ? (
                                  s.evaluacion?.decision_interna ?? s.decision
                                ).toLowerCase()
                              : 'pendiente'}
                          </span>
                        </span>
                      </td>
                    </tr>
                  )
                })}
                {!cargando && cola.length === 0 && !error && (
                  <tr>
                    <td
                      colSpan={6}
                      className="px-5 py-10 text-center text-slate-500"
                    >
                      No hay solicitudes registradas.
                    </td>
                  </tr>
                )}
                {cargando && (
                  <tr>
                    <td
                      colSpan={6}
                      className="px-5 py-10 text-center text-slate-500"
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
  icon: typeof Inbox
  label: string
  value: string
  tone?: 'brand' | 'emerald' | 'amber'
}) {
  const tones = {
    brand: 'bg-brand-50 text-brand-600',
    emerald: 'bg-emerald-50 text-emerald-600',
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

function Accion({
  to,
  icon: Icon,
  titulo,
  detalle,
}: {
  to: string
  icon: typeof FilePlus2
  titulo: string
  detalle: string
}) {
  return (
    <Link
      to={to}
      className="flex items-center gap-3 rounded-xl border border-slate-200 p-4 hover:border-brand-500/40 hover:bg-brand-50/40 transition"
    >
      <div className="h-10 w-10 rounded-xl bg-brand-50 text-brand-600 grid place-items-center shrink-0">
        <Icon size={18} />
      </div>
      <div className="min-w-0">
        <p className="font-medium text-slate-900">{titulo}</p>
        <p className="text-xs text-slate-500">{detalle}</p>
      </div>
    </Link>
  )
}
