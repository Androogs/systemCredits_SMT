import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Encabezado from '../widgets/app-shell/Encabezado'
import Tarjeta from '../shared/ui/Tarjeta'
import { FilasSkeleton } from '../shared/ui/Skeleton'
import InsigniaEstado from '../entities/credit/ui/InsigniaEstado'
import { currency, dateShort } from '../shared/lib/formatters'
import { useRol } from '../shared/lib/sesion'
import {
  estadoParaVista,
  etiquetaSolicitud,
  numero,
  ESTADOS_RETOMABLES,
  OCUPACION_LABELS,
  useSolicitudes,
  type EstadoVisual,
} from '../entities/credit/model/solicitudesPanel'
import {
  ChevronLeft,
  ChevronRight,
  Play,
  Search,
  RefreshCw,
} from 'lucide-react'

const TAMANOS_PAGINA = [10, 25, 50] as const

export default function Solicitudes() {
  const navigate = useNavigate()
  const rol = useRol()
  const vistaBinaria = rol !== 'admin'
  // Columna "Asesor" para admin, aliado (reporte de comisiones por
  // radicador) y concesionario (administra los asesores de su sede);
  // para el asesor es redundante — todo es suyo.
  const mostrarAsesor =
    rol === 'admin' || rol === 'aliado' || rol === 'concesionario'
  const {
    datos: solicitudes,
    cargando,
    error,
    recargar,
  } = useSolicitudes({
    limite: 200,
  })
  const [q, setQ] = useState('')
  const [estado, setEstado] = useState<'' | EstadoVisual>('')
  const [ocupacion, setOcupacion] = useState('')
  const [pagina, setPagina] = useState(1)
  const [porPagina, setPorPagina] = useState<number>(10)

  const retomar = (idSolicitud: string) =>
    navigate('/nueva-solicitud', { state: { retomarId: idSolicitud } })

  const filtradas = solicitudes.filter((s) => {
    const texto =
      `${s.num_solicitud} ${s.nombre_cliente} ${s.num_cedula} ${s.linea_credito ?? ''} ${s.destino_credito ?? ''}`.toLowerCase()
    if (q && !texto.includes(q.toLowerCase())) return false
    if (estado && estadoParaVista(s) !== estado) return false
    if (ocupacion && s.ocupacion !== ocupacion) return false
    return true
  })

  const totalPaginas = Math.max(1, Math.ceil(filtradas.length / porPagina))
  const paginaActual = Math.min(pagina, totalPaginas)
  const desde = (paginaActual - 1) * porPagina
  const visibles = filtradas.slice(desde, desde + porPagina)
  const columnas = (vistaBinaria ? 8 : 9) + (mostrarAsesor ? 1 : 0)

  const cambiarFiltro = (accion: () => void) => {
    accion()
    setPagina(1)
  }

  return (
    <>
      <Encabezado
        title="Solicitudes"
        subtitle="Consulta y filtra el histórico de evaluaciones"
        actions={
          <button
            onClick={() => recargar()}
            className="btn-ghost"
            type="button"
          >
            <RefreshCw size={16} aria-hidden="true" /> Actualizar
          </button>
        }
      />
      <div className="p-6 space-y-4 overflow-auto">
        <Tarjeta>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="relative sm:col-span-2">
              <Search
                size={16}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
              />
              <input
                aria-label="Buscar solicitudes"
                className="input-base pl-9"
                placeholder="Buscar por número, cliente, cédula, línea…"
                value={q}
                onChange={(e) => cambiarFiltro(() => setQ(e.target.value))}
              />
            </div>
            <select
              aria-label="Filtrar solicitudes por estado"
              className="input-base"
              value={estado}
              onChange={(e) =>
                cambiarFiltro(() =>
                  setEstado(e.target.value as '' | EstadoVisual),
                )
              }
            >
              <option value="">Todos los estados</option>
              <option value="APROBADO">Aprobado</option>
              <option value="RECHAZADO">Rechazado</option>
              <option value="PENDIENTE">Pendiente de evaluación</option>
            </select>
            <select
              aria-label="Filtrar solicitudes por ocupación"
              className="input-base"
              value={ocupacion}
              onChange={(e) =>
                cambiarFiltro(() => setOcupacion(e.target.value))
              }
            >
              <option value="">Todas las ocupaciones</option>
              {Object.entries(OCUPACION_LABELS).map(([valor, etiqueta]) => (
                <option key={valor} value={valor}>
                  {etiqueta}
                </option>
              ))}
            </select>
          </div>
        </Tarjeta>

        {error && (
          <Tarjeta className="border-red-200 bg-red-50/40 text-sm text-red-800">
            <p role="alert">No se pudieron cargar las solicitudes: {error}</p>
          </Tarjeta>
        )}
        <p className="sr-only" role="status" aria-live="polite">
          {cargando
            ? 'Cargando solicitudes'
            : `${filtradas.length} solicitudes encontradas`}
        </p>

        <Tarjeta className="p-0">
          <div
            className="overflow-x-auto"
            role="region"
            aria-label="Tabla de solicitudes"
            tabIndex={0}
          >
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-slate-500 border-b border-slate-200">
                  <th scope="col" className="px-5 py-3">
                    N°
                  </th>
                  <th scope="col" className="px-5 py-3">
                    Solicitante
                  </th>
                  <th scope="col" className="px-5 py-3">
                    Documento
                  </th>
                  <th scope="col" className="px-5 py-3">
                    Línea / destino
                  </th>
                  <th scope="col" className="px-5 py-3">
                    Fecha de solicitud
                  </th>
                  {mostrarAsesor && (
                    <th scope="col" className="px-5 py-3">
                      Asesor
                    </th>
                  )}
                  {!vistaBinaria && (
                    <th scope="col" className="px-5 py-3 text-right">
                      Score
                    </th>
                  )}
                  <th scope="col" className="px-5 py-3 text-right">
                    Cupo sugerido
                  </th>
                  <th scope="col" className="px-5 py-3">
                    Estado
                  </th>
                  <th scope="col" className="px-5 py-3">
                    Acciones
                  </th>
                </tr>
              </thead>
              <tbody aria-busy={cargando}>
                {visibles.map((s) => {
                  const cupo = numero(s.evaluacion?.cupo_sugerido)
                  const mostrarCupo =
                    cupo != null && estadoParaVista(s) === 'APROBADO'
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
                      <td className="px-5 py-3">{s.num_cedula}</td>
                      <td className="px-5 py-3 text-slate-600">
                        {[s.linea_credito, s.destino_credito]
                          .filter(Boolean)
                          .join(' · ') || '—'}
                      </td>
                      <td className="px-5 py-3 text-slate-600 whitespace-nowrap">
                        {dateShort(s.fecha_hora)}
                      </td>
                      {mostrarAsesor && (
                        <td className="px-5 py-3 text-slate-600 whitespace-nowrap">
                          {s.nombre_asesor ?? '—'}
                        </td>
                      )}
                      {!vistaBinaria && (
                        <td className="px-5 py-3 text-right font-medium tabular-nums">
                          {s.evaluacion?.score != null
                            ? Number(s.evaluacion.score)
                            : '—'}
                        </td>
                      )}
                      <td className="px-5 py-3 text-right tabular-nums">
                        {mostrarCupo ? currency(cupo) : '—'}
                      </td>
                      <td className="px-5 py-3">
                        <span className="inline-flex items-center gap-2">
                          <InsigniaEstado status={estadoParaVista(s)} />
                          {/* La decisión interna del motor solo la ve el
                              administrador, y solo cuando difiere de la
                              insignia (evaluaciones históricas). */}
                          {!vistaBinaria &&
                            s.decision != null &&
                            s.decision.toLowerCase() !==
                              estadoParaVista(s).toLowerCase() && (
                              <span className="text-xs text-slate-600">
                                {s.decision === 'perfil_gris'
                                  ? (s.evaluacion?.decision_interna ??
                                    'Perfil gris')
                                  : s.decision}
                              </span>
                            )}
                        </span>
                      </td>
                      <td className="px-5 py-3">
                        {ESTADOS_RETOMABLES.has(s.estado) && (
                          <button
                            type="button"
                            className="btn-ghost inline-flex items-center gap-1 px-2 py-1 text-xs"
                            title="Continuar la originación donde quedó"
                            onClick={() => retomar(s.id_solicitud)}
                          >
                            <Play size={13} aria-hidden="true" /> Continuar
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}
                {!cargando && filtradas.length === 0 && !error && (
                  <tr>
                    <td
                      colSpan={columnas}
                      className="px-5 py-10 text-center text-slate-500"
                    >
                      {solicitudes.length === 0
                        ? 'Aún no hay solicitudes registradas. Crea una desde Nueva solicitud.'
                        : 'Sin resultados para los filtros aplicados.'}
                    </td>
                  </tr>
                )}
                {cargando && <FilasSkeleton filas={5} columnas={columnas} />}
              </tbody>
            </table>
          </div>
          {!cargando && filtradas.length > 0 && (
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 px-5 py-3 text-sm text-slate-600">
              <p aria-live="polite">
                Mostrando {desde + 1}–{desde + visibles.length} de{' '}
                {filtradas.length}
                {filtradas.length !== solicitudes.length &&
                  ` (de ${solicitudes.length} totales)`}
              </p>
              <div className="flex items-center gap-3">
                <select
                  aria-label="Solicitudes por página"
                  className="input-base w-auto py-1.5 text-xs"
                  value={porPagina}
                  onChange={(e) =>
                    cambiarFiltro(() => setPorPagina(Number(e.target.value)))
                  }
                >
                  {TAMANOS_PAGINA.map((n) => (
                    <option key={n} value={n}>
                      {n} por página
                    </option>
                  ))}
                </select>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    className="btn-ghost !px-2 !py-1.5"
                    aria-label="Página anterior"
                    disabled={paginaActual <= 1}
                    onClick={() => setPagina(paginaActual - 1)}
                  >
                    <ChevronLeft size={16} />
                  </button>
                  <span className="min-w-16 text-center text-xs">
                    {paginaActual} / {totalPaginas}
                  </span>
                  <button
                    type="button"
                    className="btn-ghost !px-2 !py-1.5"
                    aria-label="Página siguiente"
                    disabled={paginaActual >= totalPaginas}
                    onClick={() => setPagina(paginaActual + 1)}
                  >
                    <ChevronRight size={16} />
                  </button>
                </div>
              </div>
            </div>
          )}
        </Tarjeta>
      </div>
    </>
  )
}
