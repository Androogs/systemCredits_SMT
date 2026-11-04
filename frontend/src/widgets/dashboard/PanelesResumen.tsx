import type { ReactNode } from 'react'
import Tarjeta from '../../shared/ui/Tarjeta'
import { number } from '../../shared/lib/formatters'
import type { FiltroPanel } from './GraficasResumen'

export interface ItemPanel {
  label: string
  valor: number
}

export interface GrupoOcupacion {
  tipo: string
  label: string
  total: number
  aprobadas: number
  rechazadas: number
  otras: number
}

/** Panel de lista rankeada (patrón "Sources/Pages" de la referencia):
    etiqueta + valor + share a la derecha y una pista delgada de 3px
    en el borde inferior de cada fila — magnitud sin bloques de color.
    `resumen` es un dato de contexto bajo el título (p. ej. promedio). */
export function PanelRanking({
  titulo,
  resumen,
  items,
  total,
  cargando,
  vacio,
  limite = 7,
}: {
  titulo: string
  resumen?: ReactNode
  items: ItemPanel[]
  total: number
  cargando: boolean
  vacio: string
  /** Filas visibles como máximo. */
  limite?: number
}) {
  const max = Math.max(1, ...items.map((i) => i.valor))
  return (
    <Tarjeta>
      <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-semibold text-slate-900">{titulo}</h3>
        {resumen}
      </div>
      <div
        role="img"
        aria-label={`${titulo}: ${items.map((i) => `${i.label}: ${i.valor}`).join(', ')}`}
      >
        {cargando ? (
          <div className="space-y-3 pt-2" aria-hidden="true">
            {[100, 85, 70].map((w) => (
              <div
                key={w}
                className="h-8 animate-pulse rounded-lg bg-slate-200"
                style={{ width: `${w}%` }}
              />
            ))}
          </div>
        ) : items.length === 0 ? (
          <p className="py-10 text-center text-sm text-slate-500">{vacio}</p>
        ) : (
          items.slice(0, limite).map((i) => {
            const pct = total ? Math.round((i.valor / total) * 100) : 0
            return (
              <div
                key={i.label}
                className="relative flex items-baseline gap-x-3 px-3 pb-3 pt-2 text-sm"
              >
                <span className="min-w-0 flex-1 truncate text-slate-700">
                  {i.label}
                </span>
                <span className="tabular-nums font-semibold text-slate-900">
                  {number(i.valor)}
                </span>
                <span className="tabular-nums w-9 text-right text-xs text-slate-400">
                  {pct}%
                </span>
                <span
                  className="absolute inset-x-3 bottom-0 h-[3px] overflow-hidden rounded-full bg-slate-100"
                  aria-hidden="true"
                >
                  <span
                    className="block h-full rounded-full bg-brand-500"
                    style={{ width: `${(i.valor / max) * 100}%` }}
                  />
                </span>
              </div>
            )
          })
        )}
      </div>
    </Tarjeta>
  )
}

/** Perfil de cliente por ocupación: participación de cada perfil con
    la composición aprobadas / rechazadas / otras debajo. Cada fila es
    un filtro del panel, igual que la dona de decisiones. */
export function PanelPerfilCliente({
  grupos,
  total,
  cargando,
  filtro,
  alternarFiltro,
}: {
  grupos: GrupoOcupacion[]
  total: number
  cargando: boolean
  filtro: FiltroPanel | null
  alternarFiltro: (f: FiltroPanel) => void
}) {
  return (
    <Tarjeta>
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
        <h3 className="font-semibold text-slate-900">Perfil de cliente</h3>
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
        aria-label={`Perfil de cliente: ${grupos.map((g) => `${g.label}: ${g.total}`).join(', ')}`}
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
        ) : grupos.length === 0 ? (
          <p className="py-10 text-center text-sm text-slate-500">
            Aún no hay solicitudes registradas.
          </p>
        ) : (
          grupos.map((g) => {
            const participacion = total
              ? Math.round((g.total / total) * 100)
              : 0
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
                className={`relative flex w-full items-center gap-x-3 rounded-lg px-3 pb-3 pt-2 text-sm transition hover:bg-slate-50 ${
                  activo
                    ? 'bg-brand-500/[.07] ring-1 ring-inset ring-brand-500/25'
                    : ''
                } ${
                  filtro?.campo === 'ocupacion' && !activo ? 'opacity-40' : ''
                }`}
              >
                <span className="min-w-0 flex-1 truncate text-left text-slate-700">
                  {g.label}
                </span>
                <span className="hidden shrink-0 text-xs text-slate-400 tabular-nums sm:inline">
                  {g.aprobadas} apr · {g.rechazadas} rec
                </span>
                <span className="w-20 shrink-0 text-right tabular-nums">
                  <span className="font-semibold text-slate-900">
                    {g.total}
                  </span>
                  <span className="text-xs text-slate-500">
                    {' '}
                    · {participacion}%
                  </span>
                </span>
                {/* Composición como track delgado al borde inferior:
                  aprobadas / rechazadas / otras en su proporción. */}
                <span
                  aria-hidden="true"
                  className="absolute inset-x-3 bottom-1 flex h-[3px] overflow-hidden rounded-full bg-slate-100"
                >
                  <span
                    className="bg-emerald-500"
                    style={{
                      width: `${(g.aprobadas / g.total) * 100}%`,
                    }}
                  />
                  <span
                    className="bg-red-400"
                    style={{
                      width: `${(g.rechazadas / g.total) * 100}%`,
                    }}
                  />
                </span>
              </button>
            )
          })
        )}
      </div>
    </Tarjeta>
  )
}
