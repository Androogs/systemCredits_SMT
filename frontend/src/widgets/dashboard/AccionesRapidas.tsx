import { Link } from 'react-router-dom'
import Tarjeta from '../../shared/ui/Tarjeta'
import { FilePlus2, Calculator, ClipboardList } from 'lucide-react'

/** Atajos operativos del asesor en el panel unificado: radicar,
    simular y revisar el historial. Solo el asesor las ve (admin usa
    los filtros dimensionales; aliado es de solo lectura). */
export default function AccionesRapidas() {
  return (
    <Tarjeta>
      <h3 className="font-semibold text-slate-900 mb-4">Acciones rápidas</h3>
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
      <div className="h-10 w-10 rounded-xl grid place-items-center bg-slate-50 text-slate-600 shrink-0">
        <Icon size={18} />
      </div>
      <div className="min-w-0">
        <p className="font-medium text-slate-900">{titulo}</p>
        <p className="text-xs text-slate-500">{detalle}</p>
      </div>
    </Link>
  )
}
