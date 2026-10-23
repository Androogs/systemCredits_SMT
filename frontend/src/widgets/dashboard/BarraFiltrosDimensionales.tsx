import { useQuery } from '@tanstack/react-query'
import { obtenerOpcionesFiltro } from '../../features/credit-origination/api/originacionApi'
import { Building2, UserRound, X } from 'lucide-react'

export interface DimensionesPanel {
  id_concesionario?: number
  id_asesor?: number
}

/** Filtros dimensionales del panel (admin y aliado): concesionario y
    asesor se envían al servidor y recalculan KPIs, gráficas, embudo y
    tabla. Las opciones llegan acotadas al alcance del usuario — el
    aliado solo ve sus sedes y sus asesores, base del reporte de
    comisiones. El select de asesor se restringe a la sede elegida. */
export default function BarraFiltrosDimensionales({
  dimensiones,
  onCambiar,
}: {
  dimensiones: DimensionesPanel
  onCambiar: (d: DimensionesPanel) => void
}) {
  const { data: opciones } = useQuery({
    queryKey: ['opciones-filtro'],
    queryFn: obtenerOpcionesFiltro,
    staleTime: 60_000,
  })

  const concesionarios = opciones?.concesionarios ?? []
  const asesores = (opciones?.asesores ?? []).filter(
    (a) =>
      dimensiones.id_concesionario == null ||
      a.id_concesionario === dimensiones.id_concesionario,
  )
  const hayFiltro =
    dimensiones.id_concesionario != null || dimensiones.id_asesor != null

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm">
      <label className="flex items-center gap-2 text-slate-600">
        <Building2 size={15} className="text-slate-400" aria-hidden="true" />
        Concesionario
        <select
          value={dimensiones.id_concesionario ?? ''}
          onChange={(e) =>
            onCambiar({
              id_concesionario: e.target.value
                ? Number(e.target.value)
                : undefined,
              // Al cambiar la sede el asesor elegido puede quedar fuera.
              id_asesor: undefined,
            })
          }
          className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-slate-700"
          aria-label="Filtrar por concesionario"
        >
          <option value="">Todos</option>
          {concesionarios.map((c) => (
            <option key={c.id_concesionario} value={c.id_concesionario}>
              {c.nombre}
            </option>
          ))}
        </select>
      </label>
      <label className="flex items-center gap-2 text-slate-600">
        <UserRound size={15} className="text-slate-400" aria-hidden="true" />
        Asesor
        <select
          value={dimensiones.id_asesor ?? ''}
          onChange={(e) =>
            onCambiar({
              ...dimensiones,
              id_asesor: e.target.value ? Number(e.target.value) : undefined,
            })
          }
          className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-slate-700"
          aria-label="Filtrar por asesor"
        >
          <option value="">Todos</option>
          {asesores.map((a) => (
            <option key={a.id_asesor} value={a.id_asesor}>
              {a.nombre}
            </option>
          ))}
        </select>
      </label>
      {hayFiltro && (
        <button
          type="button"
          onClick={() => onCambiar({})}
          className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600 hover:bg-slate-200"
        >
          <X size={12} /> Quitar filtros
        </button>
      )}
    </div>
  )
}
