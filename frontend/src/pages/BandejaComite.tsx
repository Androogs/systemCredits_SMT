import { useMemo } from 'react'
import { Link, Navigate } from 'react-router-dom'
import Encabezado from '../widgets/app-shell/Encabezado'
import Tarjeta from '../shared/ui/Tarjeta'
import { FilasSkeleton } from '../shared/ui/Skeleton'
import {
  etiquetaSolicitud,
  OCUPACION_LABELS,
  useSolicitudes,
} from '../entities/credit/model/solicitudesPanel'
import { currency, dateShort } from '../shared/lib/formatters'
import { useRol } from '../shared/lib/sesion'
import { CheckCircle2, Clock, Gavel, RefreshCw } from 'lucide-react'

const MS_DIA = 86_400_000

/** Días completos en revisión (aprox.: desde la radicación de la solicitud). */
function diasEnRevision(fechaIso: string): number {
  const t = new Date(fechaIso).getTime()
  if (!Number.isFinite(t)) return 0
  return Math.max(0, Math.floor((Date.now() - t) / MS_DIA))
}

function etiquetaAntiguedad(dias: number): string {
  if (dias <= 0) return 'Hoy'
  if (dias === 1) return '1 día'
  return `${dias} días`
}

function tonoAntiguedad(dias: number): string {
  if (dias >= 3) return 'bg-red-100 text-red-800'
  if (dias >= 1) return 'bg-amber-100 text-amber-800'
  return 'bg-slate-100 text-slate-600'
}

/**
 * Bandeja del comité de crédito: las solicitudes que el motor dejó en
 * `en_revision` (causales E / requiere codeudor) esperando decisión
 * manual. Solo la ve el administrador; el asesor gestiona pero no
 * resuelta excepciones de política.
 */
export default function BandejaComite() {
  const esAsesor = useRol() === 'asesor'
  const {
    datos: solicitudes,
    cargando,
    error,
    recargar,
  } = useSolicitudes({ limite: 200 })

  const pendientes = useMemo(
    () =>
      solicitudes
        .filter((s) => s.estado === 'en_revision')
        .sort(
          (a, b) =>
            new Date(a.fecha_hora).getTime() - new Date(b.fecha_hora).getTime(),
        ),
    [solicitudes],
  )

  if (esAsesor) {
    return <Navigate to="/solicitudes" replace />
  }

  return (
    <>
      <Encabezado
        title="Bandeja del comité"
        subtitle="Solicitudes que el motor no resolvió automáticamente"
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
        <Tarjeta className="flex items-center gap-4">
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-amber-100 text-amber-700">
            <Gavel size={20} aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-slate-900">
              {cargando
                ? 'Consultando casos pendientes…'
                : pendientes.length === 0
                  ? 'El comité está al día'
                  : `${pendientes.length} caso${pendientes.length === 1 ? '' : 's'} esperando decisión`}
            </p>
            <p className="text-xs text-slate-500">
              Causales de estudio (E) y perfiles que requieren codeudor. La
              decisión se toma en la página de resultado de cada solicitud.
            </p>
          </div>
        </Tarjeta>

        {error && (
          <Tarjeta className="border-red-200 bg-red-50/40 text-sm text-red-800">
            <p role="alert">No se pudieron cargar las solicitudes: {error}</p>
          </Tarjeta>
        )}

        <Tarjeta className="p-0">
          <div
            className="overflow-x-auto"
            role="region"
            aria-label="Casos pendientes del comité"
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
                    Ocupación
                  </th>
                  <th scope="col" className="px-5 py-3">
                    Decisión del motor
                  </th>
                  <th scope="col" className="px-5 py-3">
                    Cupo calculado
                  </th>
                  <th scope="col" className="px-5 py-3">
                    Radicada
                  </th>
                  <th scope="col" className="px-5 py-3">
                    En revisión
                  </th>
                  <th scope="col" className="px-5 py-3">
                    <span className="sr-only">Acción</span>
                  </th>
                </tr>
              </thead>
              <tbody aria-busy={cargando}>
                {pendientes.map((s) => {
                  const dias = diasEnRevision(s.fecha_hora)
                  const cupo = s.evaluacion?.cupo_sugerido
                  return (
                    <tr
                      key={s.id_solicitud}
                      className="border-b border-slate-100 hover:bg-slate-50"
                    >
                      <td className="px-5 py-3 font-medium">
                        <Link
                          to={`/solicitudes/${s.id_solicitud}/resultado`}
                          className="text-brand-600 hover:underline"
                        >
                          {etiquetaSolicitud(s)}
                        </Link>
                      </td>
                      <td className="px-5 py-3 whitespace-nowrap">
                        {s.nombre_cliente}
                        <span className="block text-xs text-slate-500">
                          {s.num_cedula}
                        </span>
                      </td>
                      <td className="px-5 py-3">
                        {s.ocupacion
                          ? (OCUPACION_LABELS[s.ocupacion] ?? s.ocupacion)
                          : '—'}
                      </td>
                      <td className="px-5 py-3">
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-800">
                          <Clock size={13} aria-hidden="true" />
                          {s.evaluacion?.decision_interna ?? 'Estudio'}
                        </span>
                      </td>
                      <td className="px-5 py-3">
                        {cupo != null ? currency(Number(cupo)) : '—'}
                      </td>
                      <td className="px-5 py-3 text-slate-600 whitespace-nowrap">
                        {dateShort(s.fecha_hora)}
                      </td>
                      <td className="px-5 py-3">
                        <span
                          className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${tonoAntiguedad(dias)}`}
                          title="Días desde la radicación"
                        >
                          {etiquetaAntiguedad(dias)}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-right">
                        <Link
                          to={`/solicitudes/${s.id_solicitud}/resultado`}
                          className="text-xs font-medium text-brand-600 hover:underline"
                        >
                          Resolver →
                        </Link>
                      </td>
                    </tr>
                  )
                })}
                {!cargando && pendientes.length === 0 && !error && (
                  <tr>
                    <td
                      colSpan={8}
                      className="px-5 py-12 text-center text-slate-500"
                    >
                      <CheckCircle2
                        size={28}
                        className="mx-auto mb-3 text-emerald-500"
                        aria-hidden="true"
                      />
                      No hay casos pendientes. Las solicitudes con causales de
                      estudio o codeudor aparecerán aquí.
                    </td>
                  </tr>
                )}
                {cargando && <FilasSkeleton filas={4} columnas={8} />}
              </tbody>
            </table>
          </div>
        </Tarjeta>
      </div>
    </>
  )
}
