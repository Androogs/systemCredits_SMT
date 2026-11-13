import {
  CheckCircle2,
  XCircle,
  Clock,
  Receipt,
  Banknote,
  Flag,
  Loader,
} from 'lucide-react'
import type { EstadoSolicitud } from '../model/solicitudesPanel'

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
  EN_PROCESO: {
    Icon: Loader,
    className: 'bg-brand-50 text-brand-800 ring-brand-500/20',
    label: 'En proceso',
  },
  FACTURADO: {
    Icon: Receipt,
    className: 'bg-violet-50 text-violet-700 ring-violet-600/20',
    label: 'Facturado',
  },
  DESEMBOLSADO: {
    Icon: Banknote,
    className: 'bg-emerald-100 text-emerald-800 ring-emerald-600/30',
    label: 'Desembolsado',
  },
  FINALIZADO: {
    Icon: Flag,
    className: 'bg-slate-200 text-slate-700 ring-slate-400/30',
    label: 'Finalizado',
  },
  RECHAZADO: {
    Icon: XCircle,
    className: 'bg-red-50 text-red-700 ring-red-600/20',
    label: 'Rechazado',
  },
  // Sin comité: el estado gris del motor se muestra como no aprobado.
  REQUIERE_REVISION: {
    Icon: XCircle,
    className: 'bg-red-50 text-red-700 ring-red-600/20',
    label: 'No aprobado',
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
  const cfg = CONFIG[status] || CONFIG.RECHAZADO
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
