import { useState } from 'react'
import { Link } from 'react-router-dom'
import Encabezado from '../widgets/app-shell/Encabezado'
import Tarjeta from '../shared/ui/Tarjeta'
import InsigniaEstado from '../entities/credit/ui/InsigniaEstado'
import { currency, dateShort } from '../shared/lib/formatters'
import {
  estadoVisual,
  etiquetaSolicitud,
  numero,
  useSolicitudes,
  type EstadoVisual,
} from '../entities/credit/model/solicitudesPanel'
import { Search, RefreshCw } from 'lucide-react'

export default function Solicitudes() {
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

  const filtradas = solicitudes.filter((s) => {
    const texto =
      `${s.num_solicitud} ${s.nombre_cliente} ${s.num_cedula} ${s.linea_credito ?? ''} ${s.destino_credito ?? ''}`.toLowerCase()
    if (q && !texto.includes(q.toLowerCase())) return false
    if (estado && estadoVisual(s) !== estado) return false
    return true
  })

  return (
    <>
      <Encabezado
        title="Solicitudes"
        subtitle="Consulta y filtra el histórico de evaluaciones"
        actions={
          <button onClick={recargar} className="btn-ghost">
            <RefreshCw size={16} /> Actualizar
          </button>
        }
      />
      <div className="p-6 space-y-4 overflow-auto">
        <Tarjeta>
          <div className="grid sm:grid-cols-3 gap-3">
            <div className="relative sm:col-span-2">
              <Search
                size={16}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
              />
              <input
                className="input-base pl-9"
                placeholder="Buscar por número, cliente, cédula, línea…"
                value={q}
                onChange={(e) => setQ(e.target.value)}
              />
            </div>
            <select
              className="input-base"
              value={estado}
              onChange={(e) => setEstado(e.target.value as '' | EstadoVisual)}
            >
              <option value="">Todos los estados</option>
              <option value="APROBADO">Aprobado</option>
              <option value="RECHAZADO">Rechazado</option>
              <option value="REQUIERE_REVISION">En revisión</option>
              <option value="PENDIENTE">Pendiente de evaluación</option>
            </select>
          </div>
        </Tarjeta>

        {error && (
          <Tarjeta className="border-red-200 bg-red-50/40 text-sm text-red-800">
            No se pudieron cargar las solicitudes: {error}
          </Tarjeta>
        )}

        <Tarjeta className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-slate-500 border-b border-slate-200">
                  <th className="px-5 py-3">N°</th>
                  <th className="px-5 py-3">Solicitante</th>
                  <th className="px-5 py-3">Documento</th>
                  <th className="px-5 py-3">Línea / destino</th>
                  <th className="px-5 py-3">Fecha de solicitud</th>
                  <th className="px-5 py-3">Score</th>
                  <th className="px-5 py-3">Cupo sugerido</th>
                  <th className="px-5 py-3">Estado</th>
                </tr>
              </thead>
              <tbody>
                {filtradas.map((s) => {
                  const cupo = numero(s.evaluacion?.cupo_sugerido)
                  const mostrarCupo =
                    cupo != null && estadoVisual(s) === 'APROBADO'
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
                      <td className="px-5 py-3 font-medium">
                        {s.evaluacion?.score != null
                          ? Number(s.evaluacion.score)
                          : '—'}
                      </td>
                      <td className="px-5 py-3">
                        {mostrarCupo ? currency(cupo) : '—'}
                      </td>
                      <td className="px-5 py-3">
                        <span className="inline-flex items-center gap-2">
                          <InsigniaEstado status={estadoVisual(s)} />
                          <span className="text-xs text-slate-600">
                            {s.decision
                              ? s.decision === 'perfil_gris'
                                ? (s.evaluacion?.decision_interna ??
                                  'Perfil gris')
                                : s.decision
                              : 'Pendiente'}
                          </span>
                        </span>
                      </td>
                    </tr>
                  )
                })}
                {!cargando && filtradas.length === 0 && !error && (
                  <tr>
                    <td
                      colSpan={8}
                      className="px-5 py-10 text-center text-slate-500"
                    >
                      {solicitudes.length === 0
                        ? 'Aún no hay solicitudes registradas. Crea una desde Nueva solicitud.'
                        : 'Sin resultados para los filtros aplicados.'}
                    </td>
                  </tr>
                )}
                {cargando && (
                  <tr>
                    <td
                      colSpan={8}
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
