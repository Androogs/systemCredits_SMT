import { useQuery } from '@tanstack/react-query'
import { obtenerOpcionesFiltro } from '../../features/credit-origination/api/originacionApi'
import { Building2, Tag, UserRound, X } from 'lucide-react'
import { SEDES_POR_MARCA } from '../../features/credit-origination/model/concesionarios'

export interface DimensionesPanel {
  id_concesionario?: number
  id_asesor?: number
  /** Filtros locales: la marca acota sedes y asesores; la sede se
      resuelve a id_concesionario cuando el backend la conoce. */
  marca?: string
  sede?: string
}

const MARCAS = Object.keys(SEDES_POR_MARCA).sort()

/** Normaliza para comparar nombres de sede/marca sin acentos ni mayúsculas. */
const norm = (s: string | null | undefined) =>
  (s ?? '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .trim()
    .replace(/\s+/g, ' ')

/** La sede del backend se nombra "<Marca> <Sede>": parte la marca del
    primer token y el resto es la sede. */
export function coincideMarcaSede(
  nombreConcesionario: string | null | undefined,
  marca?: string,
  sede?: string,
): boolean {
  if (!marca) return true
  const nombre = norm(nombreConcesionario)
  const m = norm(marca)
  if (!nombre.startsWith(m)) return false
  if (!sede) return true
  return nombre.slice(m.length).trim() === norm(sede)
}

/** Filtros dimensionales del panel (admin y aliado): la marca habilita
    el filtro de sede con su catálogo comercial; sin sede elegida se
    acumulan todas las sedes de la marca. Asesor se restringe a la
    marca/sede y sede+asesor viajan al servidor para recalcular KPIs,
    gráficas, embudo y tabla. */
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
  const sedesDeMarca = dimensiones.marca
    ? (SEDES_POR_MARCA[dimensiones.marca] ?? [])
    : []

  /** Resuelve la sede elegida al concesionario del backend por nombre. */
  const resolverConcesionario = (marca?: string, sede?: string) => {
    const coincidencias = concesionarios.filter((c) =>
      coincideMarcaSede(c.nombre, marca, sede),
    )
    return coincidencias.length === 1
      ? coincidencias[0].id_concesionario
      : undefined
  }

  const asesores = (opciones?.asesores ?? []).filter((a) => {
    if (!dimensiones.marca) return true
    const sede = concesionarios.find(
      (c) => c.id_concesionario === a.id_concesionario,
    )
    return (
      sede != null &&
      coincideMarcaSede(sede.nombre, dimensiones.marca, dimensiones.sede)
    )
  })
  const hayFiltro =
    dimensiones.marca != null ||
    dimensiones.id_concesionario != null ||
    dimensiones.id_asesor != null

  const select =
    'rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-slate-700'

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm">
      <label className="flex items-center gap-2 text-slate-600">
        <Tag size={15} className="text-slate-400" aria-hidden="true" />
        Marca
        <select
          value={dimensiones.marca ?? ''}
          onChange={(e) =>
            onCambiar({
              // Al cambiar la marca, sede y asesor quedan fuera.
              marca: e.target.value || undefined,
            })
          }
          className={select}
          aria-label="Filtrar por marca"
        >
          <option value="">Todas</option>
          {MARCAS.map((m) => (
            <option key={m} value={m}>
              {m.toUpperCase()}
            </option>
          ))}
        </select>
      </label>
      <label className="flex items-center gap-2 text-slate-600">
        <Building2 size={15} className="text-slate-400" aria-hidden="true" />
        Sede
        <select
          value={dimensiones.sede ?? ''}
          disabled={!dimensiones.marca}
          onChange={(e) => {
            const sede = e.target.value || undefined
            onCambiar({
              ...dimensiones,
              sede,
              id_concesionario: resolverConcesionario(dimensiones.marca, sede),
              // Al cambiar la sede el asesor elegido puede quedar fuera.
              id_asesor: undefined,
            })
          }}
          className={`${select} disabled:opacity-50`}
          aria-label="Filtrar por sede"
        >
          <option value="">Todos</option>
          {sedesDeMarca.map((s) => (
            <option key={s} value={s}>
              {s}
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
          className={select}
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
