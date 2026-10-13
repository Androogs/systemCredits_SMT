import { useParams, Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import Encabezado from '../widgets/app-shell/Encabezado'
import Tarjeta from '../shared/ui/Tarjeta'
import Skeleton from '../shared/ui/Skeleton'
import CampoNumerico from '../shared/ui/CampoNumerico'
import {
  ApiError,
  obtenerSolicitud,
  resolverSolicitud,
  type SolicitudDetalleApi,
} from '../features/credit-origination/api/originacionApi'
import {
  estadoParaVista,
  etiquetaSolicitud,
  numero,
} from '../entities/credit/model/solicitudesPanel'
import { currency, dateShort } from '../shared/lib/formatters'
import { useRol } from '../shared/lib/sesion'
import type { EstadoSolicitud } from '../entities/credit/model/underwritingEngine'
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  FileSearch,
  Clock,
  ListChecks,
} from 'lucide-react'
import type { ReactNode } from 'react'

const CONFIG: Record<
  EstadoSolicitud,
  {
    Icon: typeof CheckCircle2
    tono: string
    titulo: string
    subtitulo: string
  }
> = {
  APROBADO: {
    Icon: CheckCircle2,
    tono: 'emerald',
    titulo: 'Solicitud aprobada',
    subtitulo:
      'El perfil del cliente cumple las políticas de crédito vigentes.',
  },
  RECHAZADO: {
    Icon: XCircle,
    tono: 'red',
    titulo: 'Solicitud rechazada',
    subtitulo:
      'La evaluación arrojó causales de rechazo según las políticas vigentes.',
  },
  REQUIERE_REVISION: {
    Icon: AlertTriangle,
    tono: 'amber',
    titulo: 'Solicitud en revisión',
    subtitulo:
      'El perfil no se resuelve de forma automática y pasa a revisión del comité.',
  },
  PENDIENTE: {
    Icon: AlertTriangle,
    tono: 'slate',
    titulo: 'Pendiente de evaluación',
    subtitulo:
      'La solicitud está radicada pero aún no ha sido evaluada por el motor.',
  },
}

const tonos: Record<string, { fondo: string; icono: string; borde: string }> = {
  emerald: {
    fondo: 'bg-emerald-50',
    icono: 'bg-emerald-600 text-white',
    borde: 'border-emerald-200',
  },
  red: {
    fondo: 'bg-red-50',
    icono: 'bg-red-600 text-white',
    borde: 'border-red-200',
  },
  amber: {
    fondo: 'bg-amber-50',
    icono: 'bg-amber-500 text-white',
    borde: 'border-amber-200',
  },
  slate: {
    fondo: 'bg-slate-50',
    icono: 'bg-slate-400 text-white',
    borde: 'border-slate-200',
  },
}

export default function Resultado() {
  const { id } = useParams()
  const consulta = useQuery<SolicitudDetalleApi>({
    queryKey: ['solicitud', id],
    queryFn: () => obtenerSolicitud(id!),
    enabled: !!id,
    retry: (count, err) =>
      !(err instanceof ApiError && err.status === 404) && count < 1,
  })
  const queryClient = useQueryClient()
  const esAsesor = useRol() === 'asesor'
  const [comentarioComite, setComentarioComite] = useState('')
  // El comité puede aprobar por un monto/plazo distinto al sugerido.
  const [montoComite, setMontoComite] = useState<number | null>(null)
  const [plazoComite, setPlazoComite] = useState<number | null>(null)
  const resolverMut = useMutation({
    mutationFn: (decision: 'aprobado' | 'rechazado') =>
      resolverSolicitud(
        id!,
        decision,
        comentarioComite || undefined,
        montoComite ?? undefined,
        plazoComite ?? undefined,
      ),
    onSuccess: (detalle) => {
      queryClient.setQueryData(['solicitud', id], detalle)
      queryClient.invalidateQueries({ queryKey: ['solicitudes'] })
      setComentarioComite('')
    },
  })

  const datos = consulta.data ?? resolverMut.data ?? null
  const cargando = consulta.isPending
  const noExiste =
    consulta.error instanceof ApiError && consulta.error.status === 404
  const error =
    consulta.error && !noExiste
      ? consulta.error instanceof Error
        ? consulta.error.message
        : 'Error consultando el resultado'
      : null

  if (cargando) {
    return (
      <>
        <Encabezado title="Resultado" subtitle="Consultando información" />
        <div
          className="space-y-6 overflow-auto p-6"
          role="status"
          aria-label="Cargando el resultado"
        >
          <Tarjeta>
            <Skeleton className="mb-4 h-6 w-1/3" />
            <Skeleton className="mb-6 h-4 w-1/2" />
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {[...Array(4)].map((_, index) => (
                <Skeleton key={index} className="h-20 rounded-xl" />
              ))}
            </div>
          </Tarjeta>
          <Tarjeta>
            <Skeleton className="mb-4 h-5 w-1/3" />
            <div className="space-y-3">
              {[...Array(5)].map((_, index) => (
                <Skeleton key={index} className="h-4 w-full" />
              ))}
            </div>
          </Tarjeta>
        </div>
      </>
    )
  }

  if (noExiste || error || !datos) {
    return (
      <>
        <Encabezado
          title={
            noExiste
              ? 'Solicitud no encontrada'
              : 'No se pudo cargar el resultado'
          }
        />
        <div className="p-6">
          {error && (
            <p role="alert" className="mb-4 text-sm text-red-700">
              No se pudo cargar el resultado: {error}
            </p>
          )}
          <Link to="/solicitudes" className="btn-ghost">
            <ArrowLeft size={16} /> Volver
          </Link>
        </div>
      </>
    )
  }

  // Al asesor solo se le muestra el resultado binario: en_revision se
  // ve como pendiente, sin exponer Estudio/Requiere Codeudor interno.
  const visual = estadoParaVista(datos, esAsesor)
  const evaluacion = datos.evaluacion
  // El asesor ve la decisión pero no el score ni las causales (dato
  // sensible del cliente); la resolución de comité es del administrador.
  const oferta =
    datos.ofertas.find((o) => o.seleccionada) ??
    datos.ofertas.find((o) => o.elegible)
  const cfg = CONFIG[visual]
  const tono = tonos[cfg.tono]
  const Icon = cfg.Icon
  const causales = datos.causales.map((c) => `${c.codigo} — ${c.descripcion}`)

  return (
    <>
      <Encabezado
        title={`Resultado de la solicitud ${etiquetaSolicitud(datos)}`}
        subtitle={`${datos.nombre_cliente} · ${dateShort(datos.fecha_hora)}`}
        actions={
          <Link to="/solicitudes" className="btn-ghost">
            <ArrowLeft size={16} /> Volver
          </Link>
        }
      />
      <div className="p-6 overflow-auto">
        <div className="max-w-3xl mx-auto space-y-6">
          <Tarjeta className={`${tono.fondo} ${tono.borde} text-center py-10`}>
            <div
              className={`mx-auto h-16 w-16 rounded-full grid place-items-center ${tono.icono}`}
            >
              <Icon size={32} strokeWidth={2.5} />
            </div>
            <h2 className="mt-5 text-2xl font-bold text-slate-900">
              {!esAsesor &&
              (evaluacion?.decision_interna === 'Estudio' ||
                evaluacion?.decision_interna === 'Requiere Codeudor')
                ? `Solicitud en estudio (${evaluacion.decision_interna})`
                : cfg.titulo}
            </h2>
            <p className="mt-2 text-sm text-slate-600 max-w-md mx-auto">
              {evaluacion
                ? cfg.subtitulo
                : 'La solicitud aún no ha sido evaluada por el motor.'}
            </p>
          </Tarjeta>

          {visual === 'APROBADO' && (
            <>
              <Tarjeta>
                <h3 className="font-semibold text-slate-900 mb-4">
                  Condiciones aprobadas
                </h3>
                <dl className="grid sm:grid-cols-2 gap-x-8 gap-y-1 text-sm">
                  <Fila
                    k="Cupo sugerido"
                    v={
                      numero(evaluacion?.cupo_sugerido) != null
                        ? currency(numero(evaluacion?.cupo_sugerido))
                        : '—'
                    }
                  />
                  <Fila
                    k="Monto aprobado"
                    v={
                      oferta?.monto_aprobado != null
                        ? currency(Number(oferta.monto_aprobado))
                        : '—'
                    }
                  />
                  <Fila
                    k="Cuota mensual"
                    v={
                      oferta?.cuota_mensual != null
                        ? currency(Number(oferta.cuota_mensual))
                        : '—'
                    }
                  />
                  <Fila
                    k="Tasa / plazo"
                    v={
                      oferta
                        ? `${oferta.tasa_ofrecida != null ? `${Number(oferta.tasa_ofrecida)}% m.v.` : '—'} · ${oferta.plazo_ofrecido ?? '—'} meses`
                        : '—'
                    }
                  />
                  {!esAsesor && (
                    <Fila
                      k="Score crediticio"
                      v={
                        evaluacion?.score != null
                          ? Number(evaluacion.score)
                          : '—'
                      }
                    />
                  )}
                  <Fila
                    k="Capacidad de pago"
                    v={
                      numero(evaluacion?.capacidad_pago) != null
                        ? currency(numero(evaluacion?.capacidad_pago))
                        : '—'
                    }
                  />
                  <Fila k="Destino" v={datos.destino_credito ?? '—'} />
                  <Fila
                    k="Oferta seleccionada"
                    v={oferta?.seleccionada ? 'Sí' : 'Pendiente'}
                  />
                </dl>
              </Tarjeta>
              <Tarjeta>
                <h3 className="font-semibold text-slate-900 mb-3">
                  Siguientes pasos
                </h3>
                <ul className="space-y-2 text-sm text-slate-700">
                  <Paso n={1}>
                    Confirmar con el cliente las condiciones y la cuota
                    acordada.
                  </Paso>
                  <Paso n={2}>
                    Generar la documentación de crédito para firma y desembolso.
                  </Paso>
                  <Paso n={3}>
                    Coordinar la entrega del vehículo con el concesionario.
                  </Paso>
                </ul>
              </Tarjeta>
            </>
          )}

          {visual === 'RECHAZADO' && (
            <>
              {!esAsesor && (
                <Tarjeta className="border-red-200">
                  <h3 className="font-semibold text-slate-900 mb-3 flex items-center gap-2">
                    <FileSearch size={18} /> Causales de rechazo
                  </h3>
                  <ul className="space-y-2 text-sm">
                    {causales.length > 0 ? (
                      causales.map((r, i) => (
                        <li key={i} className="flex gap-3 text-slate-700">
                          <XCircle
                            size={17}
                            className="text-red-600 shrink-0 mt-0.5"
                          />
                          <span>{r}</span>
                        </li>
                      ))
                    ) : (
                      <li className="text-slate-500">
                        Sin causales registradas.
                      </li>
                    )}
                  </ul>
                </Tarjeta>
              )}
              <Tarjeta>
                <h3 className="font-semibold text-slate-900 mb-3">
                  Recomendaciones
                </h3>
                <ul className="space-y-2 text-sm text-slate-700">
                  <Paso n={1}>
                    Verificar las causales con el reporte de la central de
                    riesgo.
                  </Paso>
                  <Paso n={2}>
                    Una nueva evaluación solo procede si la situación del
                    cliente cambió.
                  </Paso>
                  <Paso n={3}>
                    Comunicar el resultado al asesor y al cliente.
                  </Paso>
                </ul>
              </Tarjeta>
            </>
          )}

          {(visual === 'REQUIERE_REVISION' || visual === 'PENDIENTE') && (
            <>
              <Tarjeta className="border-amber-200">
                <h3 className="font-semibold text-slate-900 mb-3 flex items-center gap-2">
                  <Clock size={18} />{' '}
                  {evaluacion
                    ? 'En estudio por el comité'
                    : 'Pendiente de evaluación'}
                </h3>
                <p className="text-sm text-slate-700">
                  {evaluacion
                    ? 'La solicitud quedó pendiente de decisión manual. El perfil cumple parcialmente las políticas y requiere análisis adicional antes de aprobar o rechazar.'
                    : 'La solicitud fue radicada y está pendiente de evaluación por el motor de decisión.'}
                </p>
                {!esAsesor && causales.length > 0 && (
                  <ul className="mt-4 space-y-2 text-sm">
                    {causales.map((r, i) => (
                      <li key={i} className="flex gap-3 text-slate-700">
                        <AlertTriangle
                          size={17}
                          className="text-amber-500 shrink-0 mt-0.5"
                        />
                        <span>{r}</span>
                      </li>
                    ))}
                  </ul>
                )}
                {datos.estado === 'en_revision' && !esAsesor && (
                  <div className="mt-5 border-t border-amber-100 pt-4">
                    <label
                      htmlFor="comentario-comite"
                      className="mb-1.5 block text-xs font-medium text-slate-600"
                    >
                      Comentario del comité (opcional)
                    </label>
                    <textarea
                      id="comentario-comite"
                      rows={2}
                      value={comentarioComite}
                      onChange={(e) => setComentarioComite(e.target.value)}
                      placeholder="Ej. Se aprueba por cliente de la casa con historial previo…"
                      className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/30"
                    />
                    <div className="mt-3 grid grid-cols-2 gap-3">
                      <label className="block">
                        <span className="mb-1 block text-xs font-medium text-slate-600">
                          Monto a aprobar (opcional)
                        </span>
                        <CampoNumerico
                          formatoMiles
                          minimo={0}
                          value={montoComite}
                          onValor={(n) => setMontoComite(n)}
                          placeholder={
                            evaluacion?.cupo_sugerido != null
                              ? `Cupo: ${Number(evaluacion.cupo_sugerido).toLocaleString('es-CO')}`
                              : 'Cupo del motor'
                          }
                          className="input-base w-full"
                        />
                        <small className="mt-0.5 block text-[11px] text-slate-500">
                          Si lo dejas vacío se aprueba el cupo sugerido del
                          motor.
                        </small>
                      </label>
                      <label className="block">
                        <span className="mb-1 block text-xs font-medium text-slate-600">
                          Plazo en meses (opcional)
                        </span>
                        <CampoNumerico
                          minimo={1}
                          value={plazoComite}
                          onValor={(n) => setPlazoComite(n)}
                          placeholder={
                            evaluacion?.plazo_cupo != null
                              ? `${evaluacion.plazo_cupo} meses`
                              : 'Plazo del cupo'
                          }
                          className="input-base w-full"
                        />
                        <small className="mt-0.5 block text-[11px] text-slate-500">
                          Plazo de la oferta generada al aprobar.
                        </small>
                      </label>
                    </div>
                    {resolverMut.isError && (
                      <p role="alert" className="mt-2 text-xs text-red-700">
                        No se pudo registrar la decisión:{' '}
                        {resolverMut.error instanceof Error
                          ? resolverMut.error.message
                          : 'error desconocido'}
                      </p>
                    )}
                    <div className="mt-3 flex gap-3">
                      <button
                        type="button"
                        disabled={resolverMut.isPending}
                        onClick={() => resolverMut.mutate('aprobado')}
                        className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-700 disabled:opacity-50"
                      >
                        <CheckCircle2 size={16} /> Aprobar por comité
                      </button>
                      <button
                        type="button"
                        disabled={resolverMut.isPending}
                        onClick={() => resolverMut.mutate('rechazado')}
                        className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-red-700 disabled:opacity-50"
                      >
                        <XCircle size={16} /> Rechazar definitivamente
                      </button>
                    </div>
                  </div>
                )}
              </Tarjeta>
              <Tarjeta>
                <h3 className="font-semibold text-slate-900 mb-3">Qué sigue</h3>
                <ul className="space-y-2 text-sm text-slate-700">
                  <Paso n={1}>
                    El comité de crédito revisa el caso y define la decisión
                    final.
                  </Paso>
                  <Paso n={2}>
                    Puede requerirse documentación adicional o un codeudor.
                  </Paso>
                  <Paso n={3}>
                    El asesor recibe el resultado y lo comunica al cliente.
                  </Paso>
                </ul>
              </Tarjeta>
            </>
          )}

          <div className="flex justify-center gap-3 pb-6">
            <Link
              to={`/solicitudes/${datos.id_solicitud}`}
              className="btn-ghost"
            >
              <ListChecks size={16} /> Ver detalle completo
            </Link>
            <Link to="/nueva-solicitud" className="btn-primary">
              Nueva solicitud
            </Link>
          </div>
        </div>
      </div>
    </>
  )
}

function Fila({ k, v }: { k: string; v: ReactNode }) {
  return (
    <div className="flex justify-between border-b border-slate-100 py-2.5 text-sm">
      <dt className="text-slate-500">{k}</dt>
      <dd className="font-medium text-slate-900">{v}</dd>
    </div>
  )
}

function Paso({ n, children }: { n: number; children: ReactNode }) {
  return (
    <li className="flex gap-3">
      <span className="h-6 w-6 shrink-0 rounded-full bg-brand-50 text-brand-600 grid place-items-center text-xs font-bold">
        {n}
      </span>
      <span>{children}</span>
    </li>
  )
}
