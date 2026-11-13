import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Tarjeta from '../../shared/ui/Tarjeta'
import { FilasSkeleton } from '../../shared/ui/Skeleton'
import InsigniaEstado from '../../entities/credit/ui/InsigniaEstado'
import { currency, dateShort } from '../../shared/lib/formatters'
import {
  estadoParaVista,
  esRetomado,
  ESTADOS_POSITIVOS_VISTA,
  etiquetaSolicitud,
  numero,
  OCUPACION_LABELS,
} from '../../entities/credit/model/solicitudesPanel'
import type { SolicitudResumenApi } from '../../features/credit-origination/api/originacionApi'
import { ChevronLeft, ChevronRight } from 'lucide-react'

const TAMANOS_PAGINA = [10, 25, 50]

/** Tabla completa de solicitudes del panel con paginación en cliente.
    El orden llega del servidor (`orden=prioridad` para la cola del
    asesor; `fecha_hora desc` para el admin). */
export default function TablaSolicitudesPanel({
  titulo = 'Solicitudes',
  solicitudes,
  cargando,
  mostrarScore,
  mostrarAsesor = false,
}: {
  titulo?: string
  solicitudes: SolicitudResumenApi[]
  cargando: boolean
  /** Score es dato interno: solo admin. */
  mostrarScore: boolean
  /** Quién radicó: admin y aliado (comisiones); el asesor no la ve
      porque todo lo que lista lo radicó él. */
  mostrarAsesor?: boolean
}) {
  const [pagina, setPagina] = useState(0)
  const [porPagina, setPorPagina] = useState(TAMANOS_PAGINA[0])
  const columnas = 6 + (mostrarScore ? 1 : 0) + (mostrarAsesor ? 1 : 0)

  // La fuente cambia con filtros/scope: volver a la primera página.
  useEffect(() => setPagina(0), [solicitudes, porPagina])

  const paginas = Math.max(1, Math.ceil(solicitudes.length / porPagina))
  const inicio = pagina * porPagina
  const filas = solicitudes.slice(inicio, inicio + porPagina)

  return (
    <Tarjeta>
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
        <h3 className="font-semibold text-slate-900">
          {titulo}
          <span className="ml-2 text-xs font-normal text-slate-500">
            {solicitudes.length} resultado
            {solicitudes.length === 1 ? '' : 's'}
          </span>
        </h3>
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
        aria-label="Tabla de solicitudes"
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
              <th scope="col" className="hidden py-3 pr-4 sm:table-cell">
                Ocupación
              </th>
              {mostrarAsesor && (
                <th scope="col" className="hidden py-3 pr-4 md:table-cell">
                  Asesor
                </th>
              )}
              {mostrarScore && (
                <th scope="col" className="py-3 pr-4 text-right">
                  Score
                </th>
              )}
              <th scope="col" className="py-3 pr-4 text-right">
                Cupo sugerido
              </th>
              <th scope="col" className="py-3 pr-4">
                Estado
              </th>
            </tr>
          </thead>
          <tbody aria-busy={cargando}>
            {filas.map((s) => {
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
                  <td className="hidden py-3 pr-4 sm:table-cell">
                    {s.ocupacion
                      ? (OCUPACION_LABELS[s.ocupacion] ?? s.ocupacion)
                      : '—'}
                  </td>
                  {mostrarAsesor && (
                    <td className="hidden py-3 pr-4 md:table-cell whitespace-nowrap">
                      {s.nombre_asesor ?? '—'}
                    </td>
                  )}
                  {mostrarScore && (
                    <td className="py-3 pr-4 text-right tabular-nums">
                      {s.evaluacion?.score != null
                        ? Number(s.evaluacion.score)
                        : '—'}
                    </td>
                  )}
                  <td className="py-3 pr-4 text-right tabular-nums">
                    {cupo != null &&
                    ESTADOS_POSITIVOS_VISTA.has(estadoParaVista(s))
                      ? currency(cupo)
                      : '—'}
                  </td>
                  <td className="py-3 pr-4">
                    <div className="flex items-center gap-1.5">
                      <InsigniaEstado status={estadoParaVista(s)} />
                      {esRetomado(s) && (
                        <span
                          title="Re-evaluada manualmente y aprobada"
                          className="inline-flex items-center whitespace-nowrap rounded-full bg-violet-50 px-2 py-0.5 text-[10px] font-semibold text-violet-700 ring-1 ring-violet-600/20"
                        >
                          Retomado
                        </span>
                      )}
                    </div>
                  </td>
                </tr>
              )
            })}
            {!cargando && filas.length === 0 && (
              <tr>
                <td
                  colSpan={columnas}
                  className="py-10 text-center text-slate-500"
                >
                  Ninguna solicitud coincide con los filtros.
                </td>
              </tr>
            )}
            {cargando && <FilasSkeleton filas={4} columnas={columnas} />}
          </tbody>
        </table>
      </div>
      {solicitudes.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500">
          <span className="tabular-nums">
            {inicio + 1}–{Math.min(inicio + porPagina, solicitudes.length)} de{' '}
            {solicitudes.length}
          </span>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1.5">
              Por página
              <select
                value={porPagina}
                onChange={(e) => setPorPagina(Number(e.target.value))}
                className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700"
                aria-label="Filas por página"
              >
                {TAMANOS_PAGINA.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setPagina((p) => Math.max(0, p - 1))}
                disabled={pagina === 0}
                aria-label="Página anterior"
                className="rounded-lg border border-slate-200 p-1.5 transition hover:bg-slate-50 disabled:opacity-40"
              >
                <ChevronLeft size={14} />
              </button>
              <span className="tabular-nums px-1">
                {pagina + 1}/{paginas}
              </span>
              <button
                type="button"
                onClick={() => setPagina((p) => Math.min(paginas - 1, p + 1))}
                disabled={pagina >= paginas - 1}
                aria-label="Página siguiente"
                className="rounded-lg border border-slate-200 p-1.5 transition hover:bg-slate-50 disabled:opacity-40"
              >
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        </div>
      )}
    </Tarjeta>
  )
}
