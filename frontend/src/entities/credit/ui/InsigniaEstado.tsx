import { CheckCircle2, XCircle, AlertTriangle, Clock } from 'lucide-react'
import type { EstadoSolicitud } from '../model/underwritingEngine'

const CONFIG: Record<
  EstadoSolicitud,
  {
    Icon: typeof CheckCircle2
    className: string
    label: string
  }
> = {
  APROBADO: {
    Icon: CheckCircle2,
    className: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
    label: 'Aprobado',
  },
  RECHAZADO: {
    Icon: XCircle,
    className: 'bg-red-50 text-red-700 ring-red-600/20',
    label: 'Rechazado',
  },
  REQUIERE_REVISION: {
    Icon: AlertTriangle,
    className: 'bg-amber-50 text-amber-700 ring-amber-600/25',
    label: 'Requiere revisión',
  },
  PENDIENTE: {
    Icon: Clock,
    className: 'bg-slate-100 text-slate-600 ring-slate-500/20',
    label: 'Pendiente de evaluación',
  },
}

export default function InsigniaEstado({
  status,
}: {
  status: EstadoSolicitud
}) {
  const cfg = CONFIG[status] || CONFIG.REQUIERE_REVISION
  const Icon = cfg.Icon

  return (
    <span
      title={cfg.label}
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${cfg.className}`}
    >
      <Icon size={13} strokeWidth={2.5} aria-hidden="true" />
      {cfg.label}
    </span>
  )
}
