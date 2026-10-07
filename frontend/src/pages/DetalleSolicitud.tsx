import { useParams, Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
import Encabezado from '../widgets/app-shell/Encabezado'
import Tarjeta from '../shared/ui/Tarjeta'
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
  type AuditoriaDetalleApi,
  type BancoApi,
  type SolicitudDetalleApi,
} from '../features/credit-origination/api/originacionApi'
import { cargarBorrador } from '../features/credit-origination/model/borrador'
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

export default function DetalleSolicitud() {
  const { id } = useParams()
  const [datos, setDatos] = useState<SolicitudDetalleApi | null>(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [noExiste, setNoExiste] = useState(false)
  const [bancos, setBancos] = useState<BancoApi[]>([])
  const [bancoAch, setBancoAch] = useState('')
  const [numeroCuenta, setNumeroCuenta] = useState('')
  const [referenciaPago, setReferenciaPago] = useState('')
  const [desembolsando, setDesembolsando] = useState(false)
  const [errorDesembolso, setErrorDesembolso] = useState<string | null>(null)
  const [evaluando, setEvaluando] = useState(false)
  const [errorEvaluacion, setErrorEvaluacion] = useState<string | null>(null)
  const [montoTomar, setMontoTomar] = useState('')
  const [plazoTomar, setPlazoTomar] = useState('')
  const [seleccionando, setSeleccionando] = useState(false)
  const [errorSeleccion, setErrorSeleccion] = useState<string | null>(null)
  const [auditoria, setAuditoria] = useState<AuditoriaDetalleApi | null>(null)
  const [jsonTab, setJsonTab] = useState<'resultado' | 'payload'>('resultado')

  function recargar() {
    if (!id) return
    return obtenerSolicitud(id).then(setDatos)
  }

  useEffect(() => {
    if (!id) return
    setCargando(true)
    obtenerSolicitud(id)
      .then(setDatos)
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 404) {
          setNoExiste(true)
        } else {
          setError(
            err instanceof Error
              ? err.message
              : 'Error consultando la solicitud',
          )
        }
      })
      .finally(() => setCargando(false))
    listarBancos()
      .then(setBancos)
      .catch(() => setBancos([]))
  }, [id])

  const idEvaluacion = datos?.evaluacion?.id_evaluacion
  useEffect(() => {
    if (!datos || idEvaluacion == null) {
      setAuditoria(null)
      return
    }
    let cancelado = false
    listarAuditoriaSolicitud(datos.id_solicitud)
      .then((lista) =>
        lista.length > 0 ? obtenerAuditoria(lista[0].evaluacion_id) : null,
      )
      .then((det) => {
        if (!cancelado) setAuditoria(det)
      })
      .catch(() => {
        if (!cancelado) setAuditoria(null)
      })
    return () => {
      cancelado = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idEvaluacion, datos?.id_solicitud])

  if (cargando) {
    return (
      <>
        <Encabezado title="Solicitud" subtitle="Cargando…" />
        <div className="p-6 text-sm text-slate-500">Cargando la solicitud…</div>
      </>
    )
  }

  if (noExiste || !datos) {
    return (
      <>
        <Encabezado
          title={noExiste ? 'Solicitud no encontrada' : 'Error'}
          subtitle={error ?? undefined}
        />
        <div className="p-6">
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
  const borrador = cargarBorrador()
  const cedulaBorrador = (
    borrador?.contexto.validacion?.numeroDocumento ?? ''
  ).replace(/\D/g, '')
  const evidencia =
    cedulaBorrador.length > 0 &&
    cedulaBorrador === datos.num_cedula.replace(/\D/g, '')
      ? (borrador?.contexto.biometria?.evidencia ?? null)
      : null

  function confirmarSeleccionOferta() {
    if (!datos || !ofertaElegible) return
    const monto = Number(montoTomar)
    const plazo = Number(plazoTomar)
    if (!(monto > 0) || !(plazo > 0)) return
    setSeleccionando(true)
    setErrorSeleccion(null)
    seleccionarOferta(
      datos.id_solicitud,
      ofertaElegible.id_oferta,
      monto,
      plazo,
    )
      .then(() => recargar())
      .catch((err: unknown) =>
        setErrorSeleccion(
          err instanceof ApiError && typeof err.detalle === 'string'
            ? err.detalle
            : err instanceof Error
              ? err.message
              : 'Error seleccionando la oferta',
        ),
      )
      .finally(() => setSeleccionando(false))
  }

  function evaluarPendiente() {
    if (!datos) return
    const plazo = datos.plazo_deseado_meses ?? 36
    const ingresos = numero(datos.datos_laborales?.ingreso_mensual) ?? 0
    const { monto } = calcularCupoSugerido(ingresos, 0, plazo)
    setEvaluando(true)
    setErrorEvaluacion(null)
    evaluarSolicitud(datos.id_solicitud, {
      saldo_financiar: Math.max(monto, 1),
      plazo,
      tasa: TASA_MENSUAL_REFERENCIA,
      consultar_experian: true,
    })
      .then(() => recargar())
      .catch((err: unknown) =>
        setErrorEvaluacion(
          err instanceof ApiError && typeof err.detalle === 'string'
            ? err.detalle
            : err instanceof Error
              ? err.message
              : 'Error evaluando la solicitud',
        ),
      )
      .finally(() => setEvaluando(false))
  }

  function confirmarDesembolso() {
    if (!datos || !bancoAch || !numeroCuenta.trim()) return
    setDesembolsando(true)
    setErrorDesembolso(null)
    registrarDesembolso(datos.id_solicitud, {
      codigo_ach_banco: bancoAch,
      numero_cuenta_cliente: numeroCuenta.trim(),
      referencia_pago: referenciaPago.trim() || undefined,
    })
      .then((d) =>
        setDatos((prev) =>
          prev ? { ...prev, estado: 'desembolsada', desembolso: d } : prev,
        ),
      )
      .catch((err: unknown) =>
        setErrorDesembolso(
          err instanceof Error
            ? err.message
            : 'Error registrando el desembolso',
        ),
      )
      .finally(() => setDesembolsando(false))
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
          {evidencia ? (
            <>
              <p className="text-xs text-slate-500 mb-4">
                Evidencia biométrica capturada en este equipo durante la
                radicación.
              </p>
              <div className="grid md:grid-cols-3 gap-6">
                <EvidenciaImagen
                  titulo="Cédula - Anverso"
                  url={evidencia.anverso}
                />
                <EvidenciaImagen
                  titulo="Cédula - Reverso"
                  url={evidencia.reverso}
                />
                <EvidenciaImagen
                  titulo="Selfie del titular"
                  url={evidencia.selfie}
                />
              </div>
              {evidencia.video && (
                <div className="mt-6 space-y-2 max-w-md">
                  <p className="text-xs uppercase text-slate-500 font-medium flex items-center gap-1">
                    <Video size={14} /> Video de validación
                  </p>
                  <div className="rounded-xl overflow-hidden border border-slate-200 bg-black">
                    <video
                      controls
                      className="w-full h-48 object-cover"
                      src={evidencia.video}
                    />
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Evidencia de prueba de vida del cliente.
                  </p>
                </div>
              )}
            </>
          ) : (
            <p className="text-sm text-slate-500 mt-1">
              Sin evidencia local registrada para esta solicitud. La captura
              biométrica (cédula, selfie y prueba de vida) se guarda en el
              equipo del asesor durante la radicación; el almacenamiento de
              documentos en el backend aún no está integrado.
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
                        <p className="text-xs text-slate-400">
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
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold flex items-center gap-2">
                <Database size={18} /> Evaluación auditada - JSON
              </h3>
              <div className="flex bg-slate-100 rounded-full p-1 text-xs">
                <button
                  onClick={() => setJsonTab('resultado')}
                  className={`px-3 py-1 rounded-full ${jsonTab === 'resultado' ? 'bg-white shadow font-medium' : 'text-slate-500'}`}
                >
                  Resultado del motor
                </button>
                <button
                  onClick={() => setJsonTab('payload')}
                  className={`px-3 py-1 rounded-full ${jsonTab === 'payload' ? 'bg-white shadow font-medium' : 'text-slate-500'}`}
                >
                  Payload enviado
                </button>
              </div>
            </div>

            <div className="rounded-xl bg-slate-950 text-slate-100 p-4 overflow-auto max-h-[380px]">
              <div className="flex justify-between items-center mb-2 text-[11px] text-slate-400">
                <span>
                  {jsonTab === 'resultado'
                    ? 'resultado_motor.json'
                    : 'solicitud_motor.json'}
                </span>
                <button
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
                  className="flex items-center gap-1 hover:text-white"
                >
                  <Download size={12} /> Descargar
                </button>
              </div>
              <pre className="text-xs leading-relaxed whitespace-pre-wrap">
                {JSON.stringify(
                  jsonTab === 'resultado'
                    ? auditoria.resultado
                    : auditoria.request,
                  null,
                  2,
                )}
              </pre>
            </div>
            <p className="mt-2 text-[11px] text-slate-500">
              Evaluación {auditoria.evaluacion_id} · origen{' '}
              {auditoria.origen_datos} · {auditoria.tiempo_ms} ms ·{' '}
              {dateShort(auditoria.fecha_evaluacion)}
            </p>
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
            {errorSeleccion && (
              <p className="mt-3 text-sm text-red-600">{errorSeleccion}</p>
            )}
            <button
              className="btn-primary mt-4"
              disabled={
                seleccionando ||
                !(Number(montoTomar) > 0) ||
                !(Number(plazoTomar) > 0)
              }
              onClick={confirmarSeleccionOferta}
            >
              {seleccionando ? 'Confirmando…' : 'Confirmar oferta seleccionada'}
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
            {errorDesembolso && (
              <p className="mt-3 text-sm text-red-600">{errorDesembolso}</p>
            )}
            <button
              className="btn-primary mt-4"
              disabled={
                desembolsando || !bancoAch || numeroCuenta.trim().length < 4
              }
              onClick={confirmarDesembolso}
            >
              {desembolsando ? 'Registrando…' : 'Confirmar desembolso'}
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
                disabled={evaluando}
              >
                {evaluando ? 'Evaluando…' : 'Evaluar con Experian'}
              </button>
            </div>
            {errorEvaluacion && (
              <p className="mt-3 text-sm text-red-600">{errorEvaluacion}</p>
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
