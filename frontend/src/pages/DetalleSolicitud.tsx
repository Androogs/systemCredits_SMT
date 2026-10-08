import { useParams, Link } from 'react-router-dom'
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Encabezado from '../widgets/app-shell/Encabezado'
import Tarjeta from '../shared/ui/Tarjeta'
import Skeleton from '../shared/ui/Skeleton'
import InsigniaEstado from '../entities/credit/ui/InsigniaEstado'
import {
  ApiError,
  evaluarSolicitud,
  listarAuditoriaSolicitud,
  listarBancos,
  obtenerAuditoria,
  obtenerSolicitud,
  registrarDesembolso,
  seleccionarOferta,
  listarEvidenciasSolicitud,
  urlEvidenciaContenido,
  type EvaluarSolicitudPayload,
  type EvidenciaApi,
  type RegistrarDesembolsoPayload,
  type SolicitudDetalleApi,
} from '../features/credit-origination/api/originacionApi'
import {
  calcularCupoSugerido,
  TASA_MENSUAL_REFERENCIA,
} from '../features/credit-origination/model/resultado-evaluacion'
import {
  estadoVisual,
  etiquetaSolicitud,
  numero,
  OCUPACION_LABELS,
} from '../entities/credit/model/solicitudesPanel'
import { currency, dateShort } from '../shared/lib/formatters'
import { cuotaAnualidad } from '../shared/lib/finanzas'
import {
  ArrowLeft,
  AlertTriangle,
  User,
  Briefcase,
  CreditCard,
  ListChecks,
  BadgePercent,
  Landmark,
  XCircle,
  CheckCircle2,
  FileImage,
  Video,
  Database,
  Eye,
  Download,
} from 'lucide-react'
import type { ReactNode } from 'react'

const CONTRATO_LABELS: Record<string, string> = {
  indefinido: 'Término indefinido',
  fijo: 'Término fijo',
  obra_labor: 'Obra o labor',
  no_aplica: 'No aplica',
}

const ETAPA_LABELS: Record<string, string> = {
  filtros_duros: 'Filtros duros',
  ingreso_final: 'Ingreso final',
  exclusion_score: 'Exclusión de score',
  perfil_score: 'Perfil de score',
  perfil_ingreso: 'Perfil de ingreso',
  matriz_decision: 'Matriz de decisión',
  capacidad_pago: 'Capacidad de pago',
}

const INDICADOR_LABELS: Record<string, string> = {
  embargos: 'Embargos vigentes',
  cancelaciones_mal_manejo: 'Cancelaciones por mal manejo',
  cartera_castigada: 'Cartera castigada',
  dudoso_recaudo: 'Obligaciones de dudoso recaudo',
  mora_60_vigente: 'Moras vigentes de 60 días o más',
  moras_30_historicas: 'Moras históricas de 30 días',
  moras_60_historicas: 'Moras históricas de 60 días',
  moras_90_historicas: 'Moras históricas de 90 días o más',
  calificaciones_negativas: 'Calificaciones negativas',
  reestructuraciones: 'Obligaciones reestructuradas',
  mora_30_vigente: 'Moras vigentes de 30 días',
  estado_documento: 'Estado del documento',
  peor_calificacion: 'Peor calificación reportada',
  documento_vigente: 'Documento vigente',
  score_codigo_exclusion: 'Código de exclusión del score',
  reportado_fallecido: 'Reporte de fallecimiento',
}

const SOLICITUD_LABELS: Record<string, string> = {
  tipo_id: 'Tipo de documento',
  numero_id: 'Número de documento',
  primer_apellido: 'Primer apellido',
  ocupacion: 'Ocupación',
  tipo_contrato: 'Tipo de contrato',
  antiguedad_meses: 'Antigüedad laboral',
  anios_camara_comercio: 'Años en Cámara de Comercio',
  fecha_nacimiento: 'Fecha de nacimiento',
  nacionalidad: 'Nacionalidad',
  tiene_multas_runt: 'Multas pendientes en RUNT',
  ingresos_mensuales: 'Ingresos mensuales declarados',
  otros_ingresos: 'Otros ingresos',
  saldo_financiar: 'Saldo a financiar',
  plazo: 'Plazo solicitado',
  tasa: 'Tasa mensual',
}

const FORMAS_MONETARIAS = new Set([
  'ingresos_mensuales',
  'otros_ingresos',
  'saldo_financiar',
])

export default function DetalleSolicitud() {
  const { id } = useParams()
  const qc = useQueryClient()
  const [bancoAch, setBancoAch] = useState('')
  const [numeroCuenta, setNumeroCuenta] = useState('')
  const [referenciaPago, setReferenciaPago] = useState('')
  const [montoTomar, setMontoTomar] = useState('')
  const [plazoTomar, setPlazoTomar] = useState('')
  const [jsonTab, setJsonTab] = useState<'resultado' | 'payload'>('resultado')

  const consultaSolicitud = useQuery<SolicitudDetalleApi>({
    queryKey: ['solicitud', id],
    queryFn: () => obtenerSolicitud(id!),
    enabled: !!id,
    retry: (count, err) =>
      !(err instanceof ApiError && err.status === 404) && count < 1,
  })
  const datos = consultaSolicitud.data ?? null
  const cargando = consultaSolicitud.isPending
  const errorConsulta = consultaSolicitud.error
  const noExiste =
    errorConsulta instanceof ApiError && errorConsulta.status === 404
  const error =
    !noExiste && errorConsulta != null
      ? errorConsulta instanceof Error
        ? errorConsulta.message
        : 'Error consultando la solicitud'
      : null

  const { data: bancos = [] } = useQuery({
    queryKey: ['bancos'],
    queryFn: listarBancos,
    staleTime: Infinity,
    retry: 0,
  })

  const { data: evidencias = [] } = useQuery<EvidenciaApi[]>({
    queryKey: ['evidencias-solicitud', datos?.id_solicitud],
    enabled: datos != null,
    queryFn: () => listarEvidenciasSolicitud(datos!.id_solicitud),
  })
  const evidenciaPorTipo = new Map(evidencias.map((e) => [e.tipo, e]))

  const idEvaluacion = datos?.evaluacion?.id_evaluacion
  const { data: auditoria = null } = useQuery({
    queryKey: ['auditoria-solicitud', datos?.id_solicitud],
    enabled: datos != null && idEvaluacion != null,
    queryFn: async () => {
      const lista = await listarAuditoriaSolicitud(datos!.id_solicitud)
      return lista.length > 0 ? obtenerAuditoria(lista[0].evaluacion_id) : null
    },
  })

  /** Tras una mutación el detalle y la lista del panel quedan frescos. */
  function invalidar() {
    qc.invalidateQueries({ queryKey: ['solicitud', id] })
    qc.invalidateQueries({ queryKey: ['solicitudes'] })
  }

  const mutEvaluar = useMutation({
    mutationFn: (payload: EvaluarSolicitudPayload) =>
      evaluarSolicitud(datos!.id_solicitud, payload),
    onSuccess: invalidar,
  })
  const mutSeleccionar = useMutation({
    mutationFn: (vars: { idOferta: number; monto: number; plazo: number }) =>
      seleccionarOferta(
        datos!.id_solicitud,
        vars.idOferta,
        vars.monto,
        vars.plazo,
      ),
    onSuccess: invalidar,
  })
  const mutDesembolso = useMutation({
    mutationFn: (payload: RegistrarDesembolsoPayload) =>
      registrarDesembolso(datos!.id_solicitud, payload),
    onSuccess: invalidar,
  })

  if (cargando) {
    return (
      <>
        <Encabezado title="Solicitud" subtitle="Consultando información" />
        <div
          className="space-y-6 overflow-auto p-6"
          role="status"
          aria-label="Cargando la solicitud"
        >
          <Tarjeta>
            <div className="space-y-4">
              <Skeleton className="h-6 w-1/3" />
              <Skeleton className="h-4 w-1/2" />
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {[...Array(4)].map((_, index) => (
                  <Skeleton key={index} className="h-20 rounded-xl" />
                ))}
              </div>
            </div>
          </Tarjeta>
          <div className="grid gap-6 lg:grid-cols-2">
            {[...Array(2)].map((_, index) => (
              <Tarjeta key={index}>
                <Skeleton className="mb-4 h-5 w-1/3" />
                <div className="space-y-3">
                  {[...Array(5)].map((__, row) => (
                    <Skeleton key={row} className="h-4 w-full" />
                  ))}
                </div>
              </Tarjeta>
            ))}
          </div>
        </div>
      </>
    )
  }

  if (noExiste || !datos) {
    return (
      <>
        <Encabezado title={noExiste ? 'Solicitud no encontrada' : 'Error'} />
        <div className="p-6">
          {error && (
            <p role="alert" className="mb-4 text-sm text-red-700">
              No se pudo cargar la solicitud: {error}
            </p>
          )}
          <Link to="/solicitudes" className="btn-ghost">
            <ArrowLeft size={16} /> Volver
          </Link>
        </div>
      </>
    )
  }

  const visual = estadoVisual(datos)
  const evaluacion = datos.evaluacion
  const cupo = numero(evaluacion?.cupo_sugerido)
  const capacidad = numero(evaluacion?.capacidad_pago)
  const endeudamiento = numero(evaluacion?.endeudamiento)
  const ofertaSeleccionada = datos.ofertas.find((o) => o.seleccionada)
  const ofertaElegible =
    ofertaSeleccionada ?? datos.ofertas.find((o) => o.elegible)
  const puedeDesembolsar =
    datos.estado === 'aprobada' && ofertaSeleccionada != null
  const puedeSeleccionarOferta =
    datos.estado === 'aprobada' && !ofertaSeleccionada && ofertaElegible != null

  const resultadoAuditoria = auditoria?.resultado ?? null
  const evidenciaFrontal = evidenciaPorTipo.get('cedula_frontal')
  const evidenciaReverso = evidenciaPorTipo.get('cedula_reverso')
  const evidenciaVideo = evidenciaPorTipo.get('video_prueba_vida')
  const hayEvidencia = evidencias.length > 0

  function mensajeError(err: unknown, fallback: string): string {
    if (err instanceof ApiError && typeof err.detalle === 'string') {
      return err.detalle
    }
    return err instanceof Error ? err.message : fallback
  }

  function confirmarSeleccionOferta() {
    if (!datos || !ofertaElegible) return
    const monto = Number(montoTomar)
    const plazo = Number(plazoTomar)
    if (!(monto > 0) || !(plazo > 0)) return
    mutSeleccionar.mutate({ idOferta: ofertaElegible.id_oferta, monto, plazo })
  }

  function evaluarPendiente() {
    if (!datos) return
    const plazo = datos.plazo_deseado_meses ?? 36
    const ingresos = numero(datos.datos_laborales?.ingreso_mensual) ?? 0
    const { monto } = calcularCupoSugerido(ingresos, 0, plazo)
    mutEvaluar.mutate({
      saldo_financiar: Math.max(monto, 1),
      plazo,
      tasa: TASA_MENSUAL_REFERENCIA,
      consultar_experian: true,
    })
  }

  function confirmarDesembolso() {
    if (!datos || !bancoAch || !numeroCuenta.trim()) return
    mutDesembolso.mutate({
      codigo_ach_banco: bancoAch,
      numero_cuenta_cliente: numeroCuenta.trim(),
      referencia_pago: referenciaPago.trim() || undefined,
    })
  }

  return (
    <>
      <Encabezado
        title={`Solicitud ${etiquetaSolicitud(datos)}`}
        subtitle={`${datos.nombre_cliente} · ${datos.num_cedula}`}
        actions={
          <>
            <Link
              to={`/solicitudes/${datos.id_solicitud}/resultado`}
              className="btn-primary"
            >
              Ver resultado
            </Link>
            <Link to="/solicitudes" className="btn-ghost">
              <ArrowLeft size={16} /> Volver
            </Link>
          </>
        }
      />
      <div className="p-6 space-y-6 overflow-auto max-w-6xl mx-auto w-full">
        <Tarjeta className="flex flex-wrap gap-4 items-center justify-between">
          <div className="flex items-center gap-4">
            <InsigniaEstado status={visual} />
            <div>
              <p className="text-xs uppercase text-slate-500">Resultado</p>
              <p className="font-semibold text-slate-900 capitalize">
                {datos.decision
                  ? (
                      evaluacion?.decision_interna ?? datos.decision
                    ).toLowerCase()
                  : 'Pendiente de evaluación'}
              </p>
            </div>
          </div>
          <div className="flex gap-8">
            <div className="text-right">
              <p className="text-xs uppercase text-slate-500">Score</p>
              <p className="text-2xl font-bold text-slate-900">
                {evaluacion?.score != null ? Number(evaluacion.score) : '—'}
              </p>
            </div>
            <div className="text-right">
              <p className="text-xs uppercase text-slate-500">Fecha</p>
              <p className="text-sm font-medium text-slate-900">
                {dateShort(datos.fecha_hora)}
              </p>
            </div>
          </div>
        </Tarjeta>

        <div className="grid sm:grid-cols-3 gap-4">
          <Metric
            label="Cupo sugerido"
            value={cupo != null && visual === 'APROBADO' ? currency(cupo) : '—'}
          />
          <Metric
            label="Capacidad de pago"
            value={capacidad != null ? currency(capacidad) : '—'}
          />
          <Metric
            label="Endeudamiento"
            value={endeudamiento != null ? `${endeudamiento.toFixed(1)}%` : '—'}
          />
        </div>

        <div className="grid lg:grid-cols-2 gap-6">
          <Tarjeta>
            <h3 className="font-semibold mb-4 flex items-center gap-2">
              <User size={18} /> Datos personales
            </h3>
            <dl className="space-y-1 text-sm">
              <Row k="Nombre" v={datos.nombre_cliente} />
              <Row k="Documento" v={datos.num_cedula} />
              <Row
                k="Ocupación"
                v={
                  datos.ocupacion
                    ? (OCUPACION_LABELS[datos.ocupacion] ?? datos.ocupacion)
                    : '—'
                }
              />
              <Row k="Línea de crédito" v={datos.linea_credito ?? '—'} />
              <Row k="Destino" v={datos.destino_credito ?? '—'} />
              <Row
                k="Plazo deseado"
                v={
                  datos.plazo_deseado_meses != null
                    ? `${datos.plazo_deseado_meses} meses`
                    : '—'
                }
              />
            </dl>
          </Tarjeta>
          <Tarjeta>
            <h3 className="font-semibold mb-4 flex items-center gap-2">
              <Briefcase size={18} /> Datos laborales
            </h3>
            <dl className="space-y-1 text-sm">
              <Row
                k="Tipo de contrato"
                v={
                  datos.datos_laborales?.tipo_contrato
                    ? (CONTRATO_LABELS[datos.datos_laborales.tipo_contrato] ??
                      datos.datos_laborales.tipo_contrato)
                    : '—'
                }
              />
              <Row
                k="Continuidad"
                v={
                  datos.datos_laborales?.meses_continuidad != null
                    ? `${datos.datos_laborales.meses_continuidad} meses`
                    : '—'
                }
              />
              <Row
                k="Ingreso declarado"
                v={
                  numero(datos.datos_laborales?.ingreso_mensual) != null
                    ? currency(numero(datos.datos_laborales?.ingreso_mensual))
                    : '—'
                }
              />
              <Row
                k="Otros ingresos"
                v={
                  numero(datos.datos_laborales?.otros_ingresos) != null
                    ? currency(numero(datos.datos_laborales?.otros_ingresos))
                    : '—'
                }
              />
              <Row
                k="Años Cámara de Comercio"
                v={datos.datos_laborales?.anios_camara_comercio ?? '—'}
              />
            </dl>
          </Tarjeta>
        </div>

        <Tarjeta>
          <h3 className="font-semibold text-slate-900 mb-1 flex items-center gap-2">
            <FileImage size={18} /> Documentos del solicitante
          </h3>
          {hayEvidencia ? (
            <>
              <p className="text-xs text-slate-500 mb-4">
                Evidencia capturada por el cliente desde su celular (enlace con
                token del paso 3).
              </p>
              <div className="grid md:grid-cols-3 gap-6">
                {evidenciaFrontal && (
                  <EvidenciaImagen
                    titulo="Cédula — frontal"
                    url={urlEvidenciaContenido(evidenciaFrontal.id_evidencia)}
                  />
                )}
                {evidenciaReverso && (
                  <EvidenciaImagen
                    titulo="Cédula — posterior"
                    url={urlEvidenciaContenido(evidenciaReverso.id_evidencia)}
                  />
                )}
              </div>
              {evidenciaVideo && (
                <div className="mt-6 space-y-2 max-w-md">
                  <p className="text-xs uppercase text-slate-500 font-medium flex items-center gap-1">
                    <Video size={14} /> Video de prueba de vida
                  </p>
                  <div className="rounded-xl overflow-hidden border border-slate-200 bg-black">
                    <video
                      controls
                      className="w-full h-48 object-cover"
                      src={urlEvidenciaContenido(evidenciaVideo.id_evidencia)}
                    />
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Cliente con la cédula junto al rostro — pendiente de
                    revisión.
                  </p>
                </div>
              )}
            </>
          ) : (
            <p className="text-sm text-slate-500 mt-1">
              Sin evidencias registradas. Desde el paso 3 de la originación
              puedes generar un enlace/QR para que el cliente las capture con su
              celular.
            </p>
          )}
        </Tarjeta>

        {evaluacion && (
          <Tarjeta>
            <h3 className="font-semibold mb-4 flex items-center gap-2">
              <CreditCard size={18} /> Evaluación del motor
            </h3>
            <dl className="grid sm:grid-cols-2 gap-x-8 gap-y-1 text-sm">
              <Row
                k="Score"
                v={evaluacion.score != null ? Number(evaluacion.score) : '—'}
              />
              <Row
                k="Perfil score / ingreso"
                v={
                  [evaluacion.perfil_score, evaluacion.perfil_ingreso]
                    .filter(Boolean)
                    .join(' · ') || '—'
                }
              />
              <Row
                k="Capacidad de pago"
                v={capacidad != null ? currency(capacidad) : '—'}
              />
              <Row
                k="Endeudamiento"
                v={endeudamiento != null ? `${endeudamiento.toFixed(1)}%` : '—'}
              />
              <Row k="Versión evaluación" v={evaluacion.version} />
              <Row
                k="Decisión interna"
                v={evaluacion.decision_interna ?? '—'}
                highlight={visual === 'APROBADO'}
              />
            </dl>
          </Tarjeta>
        )}

        {resultadoAuditoria && (
          <div className="grid lg:grid-cols-2 gap-6">
            <Tarjeta>
              <h3 className="font-semibold mb-4 flex items-center gap-2">
                <CreditCard size={18} /> Capacidad de pago
              </h3>
              <dl className="grid sm:grid-cols-2 gap-x-8 gap-y-1 text-sm">
                <Row
                  k="Ingreso final"
                  v={currency(Number(resultadoAuditoria.ingreso_final))}
                />
                <Row
                  k="Fuente del ingreso"
                  v={resultadoAuditoria.fuente_ingreso_final}
                />
                <Row
                  k="Endeudamiento"
                  v={`${Number(resultadoAuditoria.endeudamiento).toFixed(1)}%`}
                />
                <Row
                  k="Disponible"
                  v={currency(Number(resultadoAuditoria.disponible))}
                  highlight
                />
                <Row
                  k="Capacidad de pago"
                  v={currency(Number(resultadoAuditoria.capacidad_pago))}
                />
                <Row
                  k="Cuota sugerida"
                  v={currency(Number(resultadoAuditoria.cuota_sugerida))}
                />
              </dl>
            </Tarjeta>
            <Tarjeta>
              <h3 className="font-semibold mb-4">Trazabilidad del motor</h3>
              <ul className="space-y-3">
                {resultadoAuditoria.trazabilidad.map((paso) => (
                  <li key={paso.etapa} className="flex gap-3 text-sm">
                    {paso.causales.length > 0 ? (
                      <XCircle
                        size={18}
                        className="shrink-0 mt-0.5 text-amber-600"
                      />
                    ) : (
                      <CheckCircle2
                        size={18}
                        className="shrink-0 mt-0.5 text-emerald-600"
                      />
                    )}
                    <div>
                      <span className="font-medium text-slate-900">
                        {ETAPA_LABELS[paso.etapa] ?? paso.etapa}
                      </span>
                      <p className="text-slate-600">{paso.resultado}</p>
                      {paso.detalle.length > 0 && (
                        <p className="text-xs text-slate-600">
                          {paso.detalle.join(' · ')}
                        </p>
                      )}
                      {paso.causales.length > 0 && (
                        <p className="text-xs font-medium text-amber-700">
                          Causales: {paso.causales.join(', ')}
                        </p>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </Tarjeta>
          </div>
        )}

        {auditoria && (
          <Tarjeta>
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <h3 className="font-semibold flex items-center gap-2">
                <Database size={18} /> Detalle de evaluación
              </h3>
              <div
                className="flex max-w-full flex-wrap bg-slate-100 rounded-full p-1 text-xs"
                role="group"
                aria-label="Información de la evaluación"
              >
                <button
                  type="button"
                  onClick={() => setJsonTab('resultado')}
                  aria-pressed={jsonTab === 'resultado'}
                  className={`px-3 py-1.5 rounded-full ${jsonTab === 'resultado' ? 'bg-white shadow font-medium' : 'text-slate-500'}`}
                >
                  Desición Final
                </button>
                <button
                  type="button"
                  onClick={() => setJsonTab('payload')}
                  aria-pressed={jsonTab === 'payload'}
                  className={`px-3 py-1.5 rounded-full ${jsonTab === 'payload' ? 'bg-white shadow font-medium' : 'text-slate-500'}`}
                >
                  Solicitud evaluada
                </button>
              </div>
            </div>

            {jsonTab === 'resultado' ? (
              <div className="space-y-5">
                <section aria-labelledby="auditoria-decision">
                  <h4
                    id="auditoria-decision"
                    className="mb-2 text-sm font-semibold text-slate-900"
                  >
                    Decisión y perfil
                  </h4>
                  <dl className="grid gap-x-8 sm:grid-cols-2 lg:grid-cols-3">
                    <Row k="Decisión" v={auditoria.resultado.decision} />
                    <Row
                      k="Decisión interna"
                      v={auditoria.resultado.decision_interna}
                    />
                    <Row
                      k="Score consultado"
                      v={auditoria.resultado.score_consultado ?? '—'}
                    />
                    <Row
                      k="Tipo de score"
                      v={auditoria.resultado.score_tipo ?? '—'}
                    />
                    <Row
                      k="Perfil de score"
                      v={auditoria.resultado.perfil_score ?? '—'}
                    />
                    <Row
                      k="Perfil de ingreso"
                      v={auditoria.resultado.perfil_ingreso ?? '—'}
                    />
                  </dl>
                </section>

                <section aria-labelledby="auditoria-ingresos">
                  <h4
                    id="auditoria-ingresos"
                    className="mb-2 text-sm font-semibold text-slate-900"
                  >
                    Ingresos y capacidad de pago
                  </h4>
                  <dl className="grid gap-x-8 sm:grid-cols-2 lg:grid-cols-3">
                    <Row
                      k="Ingreso reportado por la evaluación"
                      v={formatCurrencyValue(auditoria.resultado.valor_ingreso)}
                    />
                    <Row
                      k="Estimación de ingreso HDC+ (Quanto)"
                      v={formatCurrencyValue(auditoria.resultado.quanto_medio)}
                    />
                    <Row
                      k="Ingreso usado por el motor"
                      v={formatCurrencyValue(auditoria.resultado.ingreso_final)}
                      highlight
                    />
                    <Row
                      k="Fuente del ingreso"
                      v={auditoria.resultado.fuente_ingreso_final}
                    />
                    <Row
                      k="Ingreso en SMMLV"
                      v={auditoria.resultado.ingreso_final_smmlv}
                    />
                    <Row
                      k="Endeudamiento"
                      v={formatPercentageValue(
                        auditoria.resultado.endeudamiento,
                      )}
                    />
                    <Row
                      k="Disponible"
                      v={formatCurrencyValue(auditoria.resultado.disponible)}
                    />
                    <Row
                      k="Capacidad de pago"
                      v={formatCurrencyValue(
                        auditoria.resultado.capacidad_pago,
                      )}
                    />
                    <Row
                      k="Cupo sugerido"
                      v={formatCurrencyValue(auditoria.resultado.cupo_sugerido)}
                    />
                    <Row
                      k="Cuota sugerida"
                      v={formatCurrencyValue(
                        auditoria.resultado.cuota_sugerida,
                      )}
                    />
                  </dl>
                </section>

                <section aria-labelledby="auditoria-historial">
                  <h4
                    id="auditoria-historial"
                    className="mb-2 text-sm font-semibold text-slate-900"
                  >
                    Indicadores del historial crediticio
                  </h4>
                  {Object.entries(auditoria.resultado.indicadores_buro).filter(
                    ([, value]) =>
                      value == null ||
                      ['string', 'number', 'boolean'].includes(typeof value),
                  ).length > 0 ? (
                    <dl className="grid gap-x-8 sm:grid-cols-2 lg:grid-cols-3">
                      {Object.entries(auditoria.resultado.indicadores_buro)
                        .filter(
                          ([, value]) =>
                            value == null ||
                            ['string', 'number', 'boolean'].includes(
                              typeof value,
                            ),
                        )
                        .map(([key, value]) => (
                          <Row
                            key={key}
                            k={INDICADOR_LABELS[key] ?? labelReadable(key)}
                            v={formatReadableValue(value)}
                          />
                        ))}
                    </dl>
                  ) : (
                    <p className="text-sm text-slate-500">
                      La auditoría no contiene indicadores de historial
                      crediticio para esta evaluación.
                    </p>
                  )}
                </section>

                {auditoria.resultado.causales.length > 0 && (
                  <section aria-labelledby="auditoria-causales">
                    <h4
                      id="auditoria-causales"
                      className="mb-2 text-sm font-semibold text-slate-900"
                    >
                      Causales de la evaluación
                    </h4>
                    <ul className="space-y-2">
                      {auditoria.resultado.causales.map((causal) => (
                        <li
                          key={causal.codigo}
                          className="rounded-lg border border-slate-200 p-3 text-sm"
                        >
                          <span className="font-semibold text-slate-900">
                            {causal.codigo}
                          </span>
                          <span className="ml-2 text-slate-700">
                            {causal.descripcion}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </section>
                )}

                {auditoria.resultado.advertencias.length > 0 && (
                  <section aria-labelledby="auditoria-advertencias">
                    <h4
                      id="auditoria-advertencias"
                      className="mb-2 text-sm font-semibold text-slate-900"
                    >
                      Advertencias
                    </h4>
                    <ul className="list-disc space-y-1 pl-5 text-sm text-amber-800">
                      {auditoria.resultado.advertencias.map(
                        (advertencia, index) => (
                          <li key={`${index}-${advertencia}`}>{advertencia}</li>
                        ),
                      )}
                    </ul>
                  </section>
                )}
              </div>
            ) : (
              <section aria-labelledby="auditoria-solicitud">
                <h4
                  id="auditoria-solicitud"
                  className="mb-2 text-sm font-semibold text-slate-900"
                >
                  Datos usados para la evaluación
                </h4>
                <dl className="grid gap-x-8 sm:grid-cols-2 lg:grid-cols-3">
                  {Object.entries(auditoria.request).map(([key, value]) => (
                    <Row
                      key={key}
                      k={SOLICITUD_LABELS[key] ?? labelReadable(key)}
                      v={
                        key === 'numero_id'
                          ? enmascararIdentificacion(value)
                          : FORMAS_MONETARIAS.has(key)
                            ? formatCurrencyValue(value)
                            : key === 'tasa'
                              ? `${formatReadableValue(value)}% m.v.`
                              : key === 'plazo'
                                ? `${formatReadableValue(value)} meses`
                                : key === 'antiguedad_meses'
                                  ? `${formatReadableValue(value)} meses`
                                  : formatReadableValue(value)
                      }
                    />
                  ))}
                </dl>
              </section>
            )}

            <p className="mt-4 rounded-lg bg-slate-50 p-3 text-xs leading-relaxed text-slate-600">
              Se muestran los resultados normalizados y los indicadores usados
              por el motor. Las respuestas JSON originales de Historia de
              Crédito y Valor Ingreso no se conservan en la auditoría.
            </p>
            <p className="mt-2 text-[11px] text-slate-500">
              Evaluación {auditoria.evaluacion_id} · origen{' '}
              {auditoria.origen_datos} · {auditoria.tiempo_ms} ms ·{' '}
              {dateShort(auditoria.fecha_evaluacion)}
            </p>
            <button
              type="button"
              onClick={() => {
                const blob = new Blob(
                  [
                    JSON.stringify(
                      jsonTab === 'resultado'
                        ? auditoria.resultado
                        : auditoria.request,
                      null,
                      2,
                    ),
                  ],
                  { type: 'application/json' },
                )
                const url = URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = `${datos.id_solicitud}_${jsonTab}.json`
                a.click()
                URL.revokeObjectURL(url)
              }}
              className="mt-3 inline-flex min-h-9 items-center gap-2 rounded-lg border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700"
            >
              <Download size={14} /> Descargar datos técnicos
            </button>
          </Tarjeta>
        )}

        {ofertaElegible && (
          <Tarjeta>
            <h3 className="font-semibold mb-4 flex items-center gap-2">
              <BadgePercent size={18} />
              {ofertaSeleccionada ? 'Oferta seleccionada' : 'Oferta elegible'}
            </h3>
            <dl className="grid sm:grid-cols-2 gap-x-8 gap-y-1 text-sm">
              <Row
                k="Monto aprobado"
                v={
                  ofertaElegible.monto_aprobado != null
                    ? currency(Number(ofertaElegible.monto_aprobado))
                    : '—'
                }
              />
              <Row
                k="Tasa ofrecida"
                v={
                  ofertaElegible.tasa_ofrecida != null
                    ? `${Number(ofertaElegible.tasa_ofrecida)}% m.v.`
                    : '—'
                }
              />
              <Row
                k="Plazo"
                v={
                  ofertaElegible.plazo_ofrecido != null
                    ? `${ofertaElegible.plazo_ofrecido} meses`
                    : '—'
                }
              />
              <Row
                k="Cuota mensual"
                v={
                  ofertaElegible.cuota_mensual != null
                    ? currency(Number(ofertaElegible.cuota_mensual))
                    : '—'
                }
              />
            </dl>
          </Tarjeta>
        )}

        {datos.desembolso && (
          <Tarjeta className="border-emerald-200 bg-emerald-50/40">
            <h3 className="font-semibold text-emerald-900 mb-4 flex items-center gap-2">
              <Landmark size={18} /> Desembolso{' '}
              {datos.desembolso.num_desembolso ?? ''}
            </h3>
            <dl className="grid sm:grid-cols-2 gap-x-8 gap-y-1 text-sm text-emerald-900">
              <Row k="Estado" v={datos.desembolso.estado} />
              <Row k="Capital" v={currency(Number(datos.desembolso.capital))} />
              <Row k="Cuota" v={currency(Number(datos.desembolso.cuota))} />
              <Row
                k="Tasa / plazo"
                v={`${Number(datos.desembolso.tasa)}% m.v. · ${datos.desembolso.plazo} meses`}
              />
              <Row k="Emisor" v={datos.desembolso.emisor} />
              <Row k="Receptor" v={datos.desembolso.receptor} />
              <Row k="Referencia" v={datos.desembolso.referencia_pago ?? '—'} />
              <Row
                k="Fecha"
                v={
                  datos.desembolso.fecha_desembolso
                    ? dateShort(datos.desembolso.fecha_desembolso)
                    : '—'
                }
              />
            </dl>
          </Tarjeta>
        )}

        {puedeSeleccionarOferta && ofertaElegible && (
          <Tarjeta>
            <h3 className="font-semibold mb-1 flex items-center gap-2">
              <BadgePercent size={18} /> Seleccionar oferta
            </h3>
            <p className="text-xs text-slate-500 mb-4">
              El cliente puede tomar un monto menor al cupo aprobado o un plazo
              más corto del ofertado. La cuota se recalcula con la tasa de la
              oferta ({Number(ofertaElegible.tasa_ofrecida ?? 0)}% m.v.).
            </p>
            <div className="grid sm:grid-cols-3 gap-3 text-sm">
              <label className="block">
                <span className="text-xs uppercase text-slate-500">
                  Monto a tomar (máx.{' '}
                  {currency(Number(ofertaElegible.monto_aprobado ?? 0))})
                </span>
                <input
                  className="input-base mt-1 w-full"
                  type="number"
                  min={0}
                  max={Number(ofertaElegible.monto_aprobado ?? 0)}
                  step={50000}
                  value={montoTomar}
                  onChange={(e) => setMontoTomar(e.target.value)}
                  placeholder={String(
                    Number(ofertaElegible.monto_aprobado ?? 0),
                  )}
                />
              </label>
              <label className="block">
                <span className="text-xs uppercase text-slate-500">
                  Plazo (máx. {ofertaElegible.plazo_ofrecido ?? 0} meses)
                </span>
                <select
                  className="input-base mt-1 w-full"
                  value={plazoTomar}
                  onChange={(e) => setPlazoTomar(e.target.value)}
                >
                  <option value="">Seleccionar…</option>
                  {[12, 18, 24, 30, 36, 42, 48]
                    .filter(
                      (p) => p <= Number(ofertaElegible.plazo_ofrecido ?? 0),
                    )
                    .map((p) => (
                      <option key={p} value={p}>
                        {p} meses
                      </option>
                    ))}
                </select>
              </label>
              <div>
                <span className="text-xs uppercase text-slate-500">
                  Cuota estimada
                </span>
                <p className="mt-1 text-lg font-bold text-slate-900">
                  {Number(montoTomar) > 0 && Number(plazoTomar) > 0
                    ? currency(
                        Math.round(
                          cuotaAnualidad(
                            Number(montoTomar),
                            Number(ofertaElegible.tasa_ofrecida ?? 0),
                            Number(plazoTomar),
                          ),
                        ),
                      )
                    : '—'}
                </p>
              </div>
            </div>
            {mutSeleccionar.error && (
              <p role="alert" className="mt-3 text-sm text-red-600">
                {mensajeError(
                  mutSeleccionar.error,
                  'Error seleccionando la oferta',
                )}
              </p>
            )}
            <button
              className="btn-primary mt-4"
              disabled={
                mutSeleccionar.isPending ||
                !(Number(montoTomar) > 0) ||
                !(Number(plazoTomar) > 0)
              }
              onClick={confirmarSeleccionOferta}
            >
              {mutSeleccionar.isPending
                ? 'Confirmando…'
                : 'Confirmar oferta seleccionada'}
            </button>
          </Tarjeta>
        )}

        {!datos.desembolso && puedeDesembolsar && (
          <Tarjeta>
            <h3 className="font-semibold mb-1 flex items-center gap-2">
              <Landmark size={18} /> Confirmar desembolso
            </h3>
            <p className="text-xs text-slate-500 mb-4">
              Formaliza el crédito sobre la oferta seleccionada y registra la
              transferencia a la cuenta de ahorros del cliente.
            </p>
            {ofertaSeleccionada && (
              <dl className="grid sm:grid-cols-4 gap-x-8 gap-y-1 text-sm mb-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                <div>
                  <dt className="text-xs uppercase text-slate-500">
                    Monto a desembolsar
                  </dt>
                  <dd className="text-lg font-bold text-slate-900">
                    {ofertaSeleccionada.monto_aprobado != null
                      ? currency(Number(ofertaSeleccionada.monto_aprobado))
                      : '—'}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase text-slate-500">Cuota</dt>
                  <dd className="text-lg font-semibold text-slate-900">
                    {ofertaSeleccionada.cuota_mensual != null
                      ? currency(Number(ofertaSeleccionada.cuota_mensual))
                      : '—'}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase text-slate-500">
                    Tasa / plazo
                  </dt>
                  <dd className="text-lg font-semibold text-slate-900">
                    {ofertaSeleccionada.tasa_ofrecida != null
                      ? `${Number(ofertaSeleccionada.tasa_ofrecida)}% m.v.`
                      : '—'}
                    {ofertaSeleccionada.plazo_ofrecido != null
                      ? ` · ${ofertaSeleccionada.plazo_ofrecido} meses`
                      : ''}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase text-slate-500">Receptor</dt>
                  <dd className="text-sm font-semibold text-slate-900 mt-1">
                    {datos.nombre_cliente}
                  </dd>
                </div>
              </dl>
            )}
            <div className="grid sm:grid-cols-3 gap-3 text-sm">
              <label className="block">
                <span className="text-xs uppercase text-slate-500">Banco</span>
                <select
                  className="input-base mt-1 w-full"
                  value={bancoAch}
                  onChange={(e) => setBancoAch(e.target.value)}
                >
                  <option value="">Seleccionar…</option>
                  {bancos.map((b) => (
                    <option key={b.id_banco} value={b.codigo_ach ?? ''}>
                      {b.nombre}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="text-xs uppercase text-slate-500">
                  Cuenta de ahorros del cliente
                </span>
                <input
                  className="input-base mt-1 w-full"
                  value={numeroCuenta}
                  onChange={(e) => setNumeroCuenta(e.target.value)}
                  placeholder="Número de cuenta"
                  inputMode="numeric"
                />
              </label>
              <label className="block">
                <span className="text-xs uppercase text-slate-500">
                  Referencia de pago (opcional)
                </span>
                <input
                  className="input-base mt-1 w-full"
                  value={referenciaPago}
                  onChange={(e) => setReferenciaPago(e.target.value)}
                  placeholder="TRX-…"
                />
              </label>
            </div>
            {mutDesembolso.error && (
              <p role="alert" className="mt-3 text-sm text-red-600">
                {mensajeError(
                  mutDesembolso.error,
                  'Error registrando el desembolso',
                )}
              </p>
            )}
            <button
              className="btn-primary mt-4"
              disabled={
                mutDesembolso.isPending ||
                !bancoAch ||
                numeroCuenta.trim().length < 4
              }
              onClick={confirmarDesembolso}
            >
              {mutDesembolso.isPending
                ? 'Registrando…'
                : 'Confirmar desembolso'}
            </button>
          </Tarjeta>
        )}

        {datos.causales.length > 0 && (
          <Tarjeta className="border-amber-200 bg-amber-50/40">
            <h3 className="font-semibold text-amber-900 mb-3 flex items-center gap-2">
              <AlertTriangle size={18} /> Causales de la evaluación
            </h3>
            <ul className="space-y-2 text-sm text-amber-900">
              {datos.causales.map((c) => (
                <li key={c.codigo} className="flex gap-3">
                  <XCircle
                    size={17}
                    className="shrink-0 mt-0.5 text-amber-600"
                  />
                  <span>
                    <span className="font-semibold">{c.codigo}</span> —{' '}
                    {c.descripcion}
                  </span>
                </li>
              ))}
            </ul>
          </Tarjeta>
        )}

        {!evaluacion && (
          <Tarjeta className="text-sm text-slate-600">
            <div className="flex flex-wrap items-center gap-3">
              <ListChecks size={18} className="text-slate-400" />
              <span className="flex-1">
                Esta solicitud aún no ha sido evaluada por el motor. Puedes
                lanzar la evaluación contra Experian desde aquí — usa la
                capacidad referencial calculada con el ingreso declarado.
              </span>
              <button
                className="btn-primary"
                onClick={evaluarPendiente}
                disabled={mutEvaluar.isPending}
              >
                {mutEvaluar.isPending ? 'Evaluando…' : 'Evaluar con Experian'}
              </button>
            </div>
            {mutEvaluar.error && (
              <p role="alert" className="mt-3 text-sm text-red-600">
                {mensajeError(mutEvaluar.error, 'Error evaluando la solicitud')}
              </p>
            )}
          </Tarjeta>
        )}
      </div>
    </>
  )
}

function Metric({ label, value }: { label: string; value: ReactNode }) {
  return (
    <Tarjeta>
      <p className="text-xs uppercase text-slate-500">{label}</p>
      <p className="mt-2 text-xl font-bold">{value}</p>
    </Tarjeta>
  )
}

function EvidenciaImagen({ titulo, url }: { titulo: string; url: string }) {
  return (
    <div className="space-y-2">
      <p className="text-xs uppercase text-slate-500 font-medium">{titulo}</p>
      <div className="group relative rounded-xl overflow-hidden border border-slate-200 bg-slate-50">
        <img src={url} alt={titulo} className="w-full h-48 object-cover" />
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center text-white text-sm gap-2 transition"
        >
          <Eye size={16} /> Ver ampliado
        </a>
      </div>
    </div>
  )
}

function Row({
  k,
  v,
  highlight = false,
}: {
  k: string
  v: ReactNode
  highlight?: boolean
}) {
  return (
    <div className="flex justify-between border-b border-slate-100 py-2.5 text-sm">
      <dt className="text-slate-500">{k}</dt>
      <dd
        className={`font-medium ${highlight ? 'text-emerald-700 font-bold' : 'text-slate-900'}`}
      >
        {v}
      </dd>
    </div>
  )
}

function formatCurrencyValue(value: unknown) {
  const amount = Number(value)
  return value == null || value === '' || !Number.isFinite(amount)
    ? '—'
    : currency(amount)
}

function formatPercentageValue(value: unknown) {
  const percentage = Number(value)
  return value == null || value === '' || !Number.isFinite(percentage)
    ? '—'
    : `${percentage.toFixed(1)}%`
}

function formatReadableValue(value: unknown): ReactNode {
  if (value == null || value === '') return 'Sin dato'
  if (typeof value === 'boolean') return value ? 'Sí' : 'No'
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value.toLocaleString('es-CO') : 'Sin dato'
  }
  if (Array.isArray(value)) {
    return value.length
      ? value.map(formatReadableValue).join(', ')
      : 'Sin registros'
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value)
    return entries.length
      ? entries
          .map(
            ([key, entryValue]) =>
              `${labelReadable(key)}: ${formatReadableValue(entryValue)}`,
          )
          .join(' · ')
      : 'Sin registros'
  }
  return typeof value === 'string' ? value : 'Sin dato'
}

function labelReadable(value: string) {
  return value
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toLocaleUpperCase('es-CO'))
}

function enmascararIdentificacion(value: unknown) {
  const identification = String(value ?? '').trim()
  if (!identification) return 'Sin dato'
  return identification.length > 4
    ? `${'•'.repeat(Math.min(identification.length - 4, 8))}${identification.slice(-4)}`
    : '•'.repeat(identification.length)
}
