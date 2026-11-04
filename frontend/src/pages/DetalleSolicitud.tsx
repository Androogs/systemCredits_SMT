import { useParams, Link, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Encabezado from '../widgets/app-shell/Encabezado'
import Tarjeta from '../shared/ui/Tarjeta'
import ConfettiCelebracion from '../shared/ui/ConfettiCelebracion'
import TarjetaColapsable from '../shared/ui/TarjetaColapsable'
import Skeleton from '../shared/ui/Skeleton'
import CampoNumerico from '../shared/ui/CampoNumerico'
import InsigniaEstado from '../entities/credit/ui/InsigniaEstado'
import {
  ApiError,
  evaluarSolicitud,
  listarAuditoriaSolicitud,
  obtenerAuditoria,
  obtenerSolicitud,
  cancelarSolicitud,
  seleccionarOferta,
  listarEvidenciasSolicitud,
  tasaMercado,
  urlEvidenciaContenido,
  urlPaqueteLegalizacion,
  type EvaluarSolicitudPayload,
  type EvidenciaApi,
  type SolicitudDetalleApi,
} from '../features/credit-origination/api/originacionApi'
import {
  calcularCupoSugerido,
  CUPO_MAXIMO,
  PRIMA_SEGURO_VIDA_PCT,
  TASA_MENSUAL_REFERENCIA,
} from '../features/credit-origination/model/resultado-evaluacion'
import {
  estadoParaVista,
  etiquetaSolicitud,
  numero,
  ESTADOS_RETOMABLES,
  OCUPACION_LABELS,
} from '../entities/credit/model/solicitudesPanel'
import { currency, dateShort, dateTime } from '../shared/lib/formatters'
import { cuotaAnualidad, tasaProductoMv } from '../shared/lib/finanzas'
import { puedeOperar, useRol } from '../shared/lib/sesion'
import {
  descargarArchivoAutenticado,
  useUrlObjetoAutenticado,
} from '../shared/lib/archivoAutenticado'
import VisorDocumento from '../features/credit-origination/ui/VisorDocumento'
import {
  ArrowLeft,
  AlertTriangle,
  User,
  Briefcase,
  Home,
  CreditCard,
  ListChecks,
  BadgePercent,
  Landmark,
  ShieldCheck,
  XCircle,
  CheckCircle2,
  FileImage,
  Video,
  Database,
  Eye,
  Download,
  History,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { MARCA } from '../shared/lib/marca'

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
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [montoTomar, setMontoTomar] = useState('')
  const [plazoTomar, setPlazoTomar] = useState('')
  // Re-evaluación con parámetros editables (solo administrador).
  const [reSaldo, setReSaldo] = useState<number | null>(null)
  const [rePlazo, setRePlazo] = useState<number | null>(null)
  const [reTasa, setReTasa] = useState('')
  const [confirmarCancelacion, setConfirmarCancelacion] = useState(false)
  const [motivoCancelar, setMotivoCancelar] = useState('')
  const [jsonTab, setJsonTab] = useState<'resultado' | 'payload'>('resultado')
  const [docPrevia, setDocPrevia] = useState<EvidenciaApi | null>(null)
  const [vista, setVista] = useState<'solicitud' | 'evaluacion' | 'gestion'>(
    'solicitud',
  )
  // El asesor gestiona la solicitud pero no ve score, causales ni la
  // auditoría del motor (dato sensible); esa vista es del administrador.
  // El aliado además es solo lectura: no ve la pestaña Gestión.
  const rol = useRol()
  const vistaBinaria = rol !== 'admin'
  const operativo = puedeOperar(rol)
  useEffect(() => {
    if (vistaBinaria && vista === 'evaluacion') setVista('solicitud')
    if (!operativo && vista === 'gestion') setVista('solicitud')
  }, [vistaBinaria, operativo, vista])

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

  const { data: evidencias = [] } = useQuery<EvidenciaApi[]>({
    queryKey: ['evidencias-solicitud', datos?.id_solicitud],
    enabled: datos != null,
    queryFn: () => listarEvidenciasSolicitud(datos!.id_solicitud),
  })

  const evidenciaPorTipo = new Map(evidencias.map((e) => [e.tipo, e]))

  const idEvaluacion = datos?.evaluacion?.id_evaluacion
  // Todas las evaluaciones de la solicitud, más reciente primero: el
  // historial deja constancia de las anteriores (p. ej. un rechazo que
  // el administrador re-evaluó con otros parámetros).
  const { data: auditorias = [] } = useQuery({
    queryKey: ['auditorias-solicitud', datos?.id_solicitud],
    // La auditoría es del administrador; para los demás el endpoint
    // responde 403 y esta consulta solo ensuciaría la consola.
    enabled: datos != null && idEvaluacion != null && !vistaBinaria,
    queryFn: () => listarAuditoriaSolicitud(datos!.id_solicitud),
  })
  const { data: auditoria = null } = useQuery({
    queryKey: ['auditoria-solicitud', auditorias[0]?.evaluacion_id],
    enabled: auditorias.length > 0,
    queryFn: () => obtenerAuditoria(auditorias[0].evaluacion_id),
  })

  // Tasa del producto = usura de consumo y ordinario vigente (SFC);
  // respaldo: la referencia fija. Es la tasa con la que se re-evalúa.
  const consultaTasa = useQuery({
    queryKey: ['tasa-mercado'],
    queryFn: tasaMercado,
    staleTime: 6 * 60 * 60_000,
    retry: 1,
  })
  const tasaOperativa =
    tasaProductoMv(consultaTasa.data?.ordinario.usura_ea) ??
    TASA_MENSUAL_REFERENCIA

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
  const mutCancelar = useMutation({
    mutationFn: (motivo: string) =>
      cancelarSolicitud(datos!.id_solicitud, motivo),
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

  const visual = estadoParaVista(datos)
  const evaluacion = datos.evaluacion
  const cupo = numero(evaluacion?.cupo_sugerido)
  const capacidad = numero(evaluacion?.capacidad_pago)
  const endeudamiento = numero(evaluacion?.endeudamiento)
  const ofertaSeleccionada = datos.ofertas.find((o) => o.seleccionada)
  const ofertaElegible =
    ofertaSeleccionada ?? datos.ofertas.find((o) => o.elegible)
  const puedeSeleccionarOferta =
    datos.estado === 'aprobada' &&
    !ofertaSeleccionada &&
    ofertaElegible != null &&
    !ofertaElegible.expirada
  const plazoMaxOferta = Number(ofertaElegible?.plazo_ofrecido ?? 0)
  const plazoInvalido =
    plazoTomar !== '' &&
    (Number(plazoTomar) < 12 || Number(plazoTomar) > plazoMaxOferta)

  // Datos del cliente capturados en la formalización (antes del OTP).
  // Solo se muestran cuando efectivamente se guardaron.
  const contacto = datos.contacto_vivienda
  const laboral = datos.datos_laborales
  const hayFormalizacion = [
    contacto?.direccion,
    contacto?.barrio,
    contacto?.ciudad,
    contacto?.estrato,
    contacto?.tipo_vivienda,
    contacto?.estado_civil,
    contacto?.zona_rural,
    contacto?.personas_a_cargo,
    contacto?.num_hijos,
    contacto?.es_cabeza_familia,
    contacto?.cuenta_bienes_raices,
    contacto?.cuenta_vehiculo,
    contacto?.tiene_moto,
    contacto?.tiene_carro,
    contacto?.primera_moto,
    contacto?.estoy_financiando,
    laboral?.nombre_empresa,
    laboral?.ciudad_empresa,
    laboral?.fecha_ingreso,
    laboral?.nivel_educativo,
    laboral?.profesion,
    laboral?.cargo,
    laboral?.actividad_comercial,
  ].some((v) => v != null && v !== '')

  const resultadoAuditoria = auditoria?.resultado ?? null
  const evidenciaFrontal = evidenciaPorTipo.get('cedula_frontal')
  const evidenciaReverso = evidenciaPorTipo.get('cedula_reverso')
  const evidenciaVideo = evidenciaPorTipo.get('video_prueba_vida')
  // Paquete de legalización: los doc_* se generan al verificar el OTP de firma.
  const documentosFirmados = evidencias.filter((e) => e.tipo.startsWith('doc_'))
  const hayEvidencia = evidencias.some((e) => !e.tipo.startsWith('doc_'))

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
    if (!(monto > 0) || !(plazo >= 12) || plazo > plazoMaxOferta) return
    mutSeleccionar.mutate({ idOferta: ofertaElegible.id_oferta, monto, plazo })
  }

  function evaluarPendiente() {
    if (!datos) return
    const plazo = datos.plazo_deseado_meses ?? 36
    const ingresos = numero(datos.datos_laborales?.ingreso_mensual) ?? 0
    const { monto } = calcularCupoSugerido(ingresos, plazo)
    mutEvaluar.mutate({
      saldo_financiar: Math.max(monto, 1),
      plazo,
      tasa: tasaOperativa,
      consultar_experian: true,
    })
  }

  // Valores por defecto de la re-evaluación: los de la evaluación vigente.
  const reSaldoDef =
    numero(evaluacion?.cupo_sugerido) ??
    Math.max(
      calcularCupoSugerido(
        numero(datos.datos_laborales?.ingreso_mensual) ?? 0,
        datos.plazo_deseado_meses ?? 24,
      ).monto,
      1,
    )
  const rePlazoDef = evaluacion?.plazo_cupo ?? datos.plazo_deseado_meses ?? 24
  const reTasaDef = (() => {
    const tasaRequest = Number(
      (auditoria?.request as Record<string, unknown> | undefined)?.tasa,
    )
    return Number.isFinite(tasaRequest) && tasaRequest > 0
      ? tasaRequest
      : tasaOperativa
  })()

  /* Vista previa de la retoma: con los valores vigentes (o los que el
     administrador digita) se estima la cuota con seguro, si cabe en la
     capacidad de pago de la evaluación y el cupo que sí pasaría con ese
     plazo y esa tasa — la misma matemática de la calculadora manual. */
  const reMontoPrev = reSaldo ?? Math.round(reSaldoDef)
  const rePlazoPrev = rePlazo ?? rePlazoDef
  const reTasaPrev = reTasa !== '' ? Number(reTasa) : reTasaDef
  const reCapacidadPrev =
    numero(resultadoAuditoria?.capacidad_pago) ?? capacidad
  const reCuotaPrev =
    reMontoPrev > 0 && rePlazoPrev > 0 && reTasaPrev > 0
      ? Math.round(
          cuotaAnualidad(reMontoPrev, reTasaPrev, rePlazoPrev) +
            (reMontoPrev * PRIMA_SEGURO_VIDA_PCT) / 100,
        )
      : null
  // Cupo que sí cabe con este plazo y tasa: cuota = monto·(anualidad + seguro)
  // ⇒ monto máx = capacidad / (anualidad + seguro).
  const reSeguroPct = PRIMA_SEGURO_VIDA_PCT / 100
  const reFactorCuota =
    rePlazoPrev > 0
      ? reTasaPrev > 0
        ? reTasaPrev /
            100 /
            (1 - Math.pow(1 + reTasaPrev / 100, -rePlazoPrev)) +
          reSeguroPct
        : 1 / rePlazoPrev + reSeguroPct
      : null
  // Capacidad pura puede dar números muy por encima del producto: el
  // cupo que de verdad cabe también queda topado por el máximo comercial.
  const reCupoPosible =
    reCapacidadPrev != null && reCapacidadPrev > 0 && reFactorCuota
      ? Math.min(CUPO_MAXIMO, Math.round(reCapacidadPrev / reFactorCuota))
      : null
  const reCupoTopadoPorCapacidad =
    reCapacidadPrev != null &&
    reFactorCuota != null &&
    reCapacidadPrev / reFactorCuota > CUPO_MAXIMO

  /** Re-corre el motor con los parámetros editados por el administrador,
      reusando el origen de datos de buró de la evaluación vigente
      (mismo escenario mock, o Experian en línea si así fue consultada). */
  function reevaluar() {
    if (!datos) return
    const origen = auditoria?.origen_datos ?? ''
    const escenarioMock = origen.startsWith('mock:')
      ? origen.slice(5).split('+')[0] || null
      : null
    mutEvaluar.mutate({
      saldo_financiar: reSaldo ?? reSaldoDef,
      plazo: rePlazo ?? rePlazoDef,
      tasa: reTasa !== '' ? Number(reTasa) : reTasaDef,
      consultar_experian: origen.startsWith('experian'),
      escenario_mock: escenarioMock,
    })
  }

  return (
    <>
      <Encabezado
        title={`Solicitud ${etiquetaSolicitud(datos)}`}
        subtitle={`${datos.nombre_cliente} · ${datos.num_cedula} · Estudio de crédito: ${MARCA.nombre}`}
        actions={
          <>
            {/* La solicitud sigue abierta en originación (sin oferta
                seleccionada ni desembolso): se retoma en el primer
                paso que quedó pendiente. */}
            {ESTADOS_RETOMABLES.has(datos.estado) && !ofertaSeleccionada && (
              <button
                type="button"
                className="btn-ghost"
                onClick={() =>
                  navigate('/nueva-solicitud', {
                    state: { retomarId: datos.id_solicitud },
                  })
                }
              >
                Continuar originación
              </button>
            )}
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
        {/* Resumen único: estado + métricas en una sola tarjeta, sin
            apilar tarjetas pequeñas que saturan la vista. */}
        <Tarjeta className="space-y-5 relative overflow-hidden">
          {visual === 'APROBADO' && <ConfettiCelebracion />}
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <InsigniaEstado status={visual} />
              <div>
                <p className="text-xs uppercase text-slate-500">Resultado</p>
                <p className="font-semibold text-slate-900 capitalize">
                  {vistaBinaria
                    ? visual === 'APROBADO'
                      ? 'Aprobado'
                      : visual === 'RECHAZADO'
                        ? 'Rechazado'
                        : 'Pendiente de evaluación'
                    : datos.decision
                      ? (
                          evaluacion?.decision_interna ?? datos.decision
                        ).toLowerCase()
                      : 'Pendiente de evaluación'}
                </p>
              </div>
            </div>
            <p className="text-sm text-slate-500">
              Radicada el{' '}
              <span className="font-medium text-slate-900">
                {dateShort(datos.fecha_hora)}
              </span>
            </p>
          </div>
          <dl className="flex flex-wrap gap-x-10 gap-y-4 border-t border-slate-100 pt-4">
            {!vistaBinaria && (
              <Campo
                k="Score"
                v={evaluacion?.score != null ? Number(evaluacion.score) : '—'}
              />
            )}
            <Campo
              k="Cupo sugerido"
              v={cupo != null && visual === 'APROBADO' ? currency(cupo) : '—'}
            />
            <Campo
              k="Capacidad de pago"
              v={capacidad != null ? currency(capacidad) : '—'}
            />
            <Campo
              k="Endeudamiento"
              v={endeudamiento != null ? `${endeudamiento.toFixed(1)}%` : '—'}
            />
          </dl>
        </Tarjeta>

        {/* Secciones del detalle */}
        <div
          className="flex flex-wrap gap-1 border-b border-slate-200"
          role="tablist"
          aria-label="Secciones del detalle"
        >
          <TabDetalle
            activo={vista === 'solicitud'}
            onClick={() => setVista('solicitud')}
          >
            Solicitud
          </TabDetalle>
          {!vistaBinaria && (
            <TabDetalle
              activo={vista === 'evaluacion'}
              onClick={() => setVista('evaluacion')}
            >
              Evaluación
            </TabDetalle>
          )}
          {operativo && (
            <TabDetalle
              activo={vista === 'gestion'}
              onClick={() => setVista('gestion')}
            >
              Gestión
            </TabDetalle>
          )}
        </div>

        {vista === 'solicitud' && (
          <>
            <div className="grid lg:grid-cols-2 gap-6">
              <Tarjeta>
                <h3 className="font-semibold mb-4 flex items-center gap-2">
                  <User size={18} /> Datos personales
                </h3>
                <dl className="grid sm:grid-cols-2 gap-x-8 gap-y-4">
                  <Campo k="Nombre" v={datos.nombre_cliente} />
                  <Campo k="Documento" v={datos.num_cedula} />
                  <Campo k="Teléfono" v={contacto?.telefono ?? '—'} />
                  <Campo k="Correo" v={contacto?.correo ?? '—'} />
                  <Campo
                    k="Ocupación"
                    v={
                      datos.ocupacion
                        ? (OCUPACION_LABELS[datos.ocupacion] ?? datos.ocupacion)
                        : '—'
                    }
                  />
                  <Campo k="Línea de crédito" v={datos.linea_credito ?? '—'} />
                  <Campo k="Destino" v={datos.destino_credito ?? '—'} />
                  <Campo
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
                  <Briefcase size={18} /> Datos laborales declarados
                </h3>
                <dl className="grid sm:grid-cols-2 gap-x-8 gap-y-4">
                  <Campo
                    k="Tipo de contrato"
                    v={
                      laboral?.tipo_contrato
                        ? (CONTRATO_LABELS[laboral.tipo_contrato] ??
                          laboral.tipo_contrato)
                        : '—'
                    }
                  />
                  <Campo
                    k="Continuidad"
                    v={
                      laboral?.meses_continuidad != null
                        ? `${laboral.meses_continuidad} meses`
                        : '—'
                    }
                  />
                  <Campo
                    k="Ingreso declarado"
                    v={
                      numero(laboral?.ingreso_mensual) != null
                        ? currency(numero(laboral?.ingreso_mensual))
                        : '—'
                    }
                  />
                  <Campo
                    k="Otros ingresos"
                    v={
                      numero(laboral?.otros_ingresos) != null
                        ? currency(numero(laboral?.otros_ingresos))
                        : '—'
                    }
                  />
                  <Campo
                    k="Años Cámara de Comercio"
                    v={laboral?.anios_camara_comercio ?? '—'}
                  />
                </dl>
              </Tarjeta>
            </div>

            {/* Datos capturados antes de la firma OTP: alimentan el
                paquete de legalización generado tras la firma. Son ~24
                campos de consulta ocasional: cerrada por defecto. */}
            {hayFormalizacion && (
              <TarjetaColapsable
                titulo={
                  <>
                    <Home size={18} /> Datos del cliente — formalización
                  </>
                }
                resumen="Residencia · personal · laboral"
              >
                <p className="text-xs text-slate-500 mb-4">
                  Capturados antes de la firma OTP; alimentan los documentos de
                  legalización.
                </p>
                <div className="grid gap-4 lg:grid-cols-2">
                  <SeccionAuditoria
                    titulo="Residencia"
                    columnas="lg:grid-cols-2"
                  >
                    <Campo k="Dirección" v={contacto?.direccion ?? '—'} />
                    <Campo k="Barrio" v={contacto?.barrio ?? '—'} />
                    <Campo k="Ciudad" v={contacto?.ciudad ?? '—'} />
                    <Campo k="Estrato" v={contacto?.estrato ?? '—'} />
                    <Campo
                      k="Tipo de vivienda"
                      v={contacto?.tipo_vivienda ?? '—'}
                    />
                    <Campo
                      k="Zona rural"
                      v={formatReadableValue(contacto?.zona_rural)}
                    />
                  </SeccionAuditoria>
                  <SeccionAuditoria
                    titulo="Personal y patrimonio"
                    columnas="lg:grid-cols-2"
                  >
                    <Campo k="Estado civil" v={contacto?.estado_civil ?? '—'} />
                    <Campo
                      k="Personas a cargo"
                      v={contacto?.personas_a_cargo ?? '—'}
                    />
                    <Campo k="Número de hijos" v={contacto?.num_hijos ?? '—'} />
                    <Campo
                      k="Cabeza de familia"
                      v={formatReadableValue(contacto?.es_cabeza_familia)}
                    />
                    <Campo
                      k="Bienes raíces"
                      v={formatReadableValue(contacto?.cuenta_bienes_raices)}
                    />
                    <Campo
                      k="Vehículo propio"
                      v={formatReadableValue(contacto?.cuenta_vehiculo)}
                    />
                    <Campo
                      k="Tiene moto / carro"
                      v={
                        contacto?.tiene_moto == null &&
                        contacto?.tiene_carro == null
                          ? '—'
                          : [
                              contacto?.tiene_moto ? 'Moto' : null,
                              contacto?.tiene_carro ? 'Carro' : null,
                            ]
                              .filter(Boolean)
                              .join(' y ') || 'No'
                      }
                    />
                    <Campo
                      k="Primera moto"
                      v={formatReadableValue(contacto?.primera_moto)}
                    />
                    <Campo
                      k="Financia"
                      v={
                        contacto?.estoy_financiando == null
                          ? '—'
                          : contacto.estoy_financiando
                            ? 'Motocicleta'
                            : 'Otro bien'
                      }
                    />
                  </SeccionAuditoria>
                  <SeccionAuditoria
                    titulo="Laboral"
                    columnas="lg:grid-cols-3"
                    className="lg:col-span-2"
                  >
                    <Campo
                      k="Empresa / entidad"
                      v={laboral?.nombre_empresa ?? '—'}
                    />
                    <Campo
                      k="Ciudad de la empresa"
                      v={laboral?.ciudad_empresa ?? '—'}
                    />
                    <Campo
                      k="Fecha de ingreso"
                      v={
                        laboral?.fecha_ingreso
                          ? dateShort(laboral.fecha_ingreso)
                          : '—'
                      }
                    />
                    <Campo
                      k="Nivel educativo"
                      v={laboral?.nivel_educativo ?? '—'}
                    />
                    <Campo k="Profesión" v={laboral?.profesion ?? '—'} />
                    <Campo k="Cargo" v={laboral?.cargo ?? '—'} />
                    <Campo
                      k="Actividad comercial"
                      v={laboral?.actividad_comercial ?? '—'}
                    />
                  </SeccionAuditoria>
                </div>
              </TarjetaColapsable>
            )}

            <TarjetaColapsable
              titulo={
                <>
                  <FileImage size={18} /> Documentos del solicitante
                </>
              }
              resumen={
                hayEvidencia
                  ? [
                      evidenciaFrontal || evidenciaReverso
                        ? `${[evidenciaFrontal, evidenciaReverso].filter(Boolean).length} imágenes`
                        : null,
                      evidenciaVideo ? '1 video' : null,
                    ]
                      .filter(Boolean)
                      .join(' · ')
                  : 'Sin evidencias'
              }
            >
              {hayEvidencia ? (
                <>
                  <p className="text-xs text-slate-500 mb-4">
                    Evidencia capturada por el cliente desde su celular (enlace
                    con token del paso 3).
                  </p>
                  <div className="grid md:grid-cols-3 gap-6">
                    {evidenciaFrontal && (
                      <EvidenciaImagen
                        titulo="Cédula — frontal"
                        url={urlEvidenciaContenido(
                          evidenciaFrontal.id_evidencia,
                        )}
                      />
                    )}
                    {evidenciaReverso && (
                      <EvidenciaImagen
                        titulo="Cédula — posterior"
                        url={urlEvidenciaContenido(
                          evidenciaReverso.id_evidencia,
                        )}
                      />
                    )}
                  </div>
                  {evidenciaVideo && (
                    <div className="mt-6 space-y-2 max-w-md">
                      <p className="text-xs uppercase text-slate-500 font-medium flex items-center gap-1">
                        <Video size={14} /> Video de prueba de vida
                      </p>
                      <div className="rounded-xl overflow-hidden border border-slate-200 bg-black">
                        <EvidenciaVideo
                          url={urlEvidenciaContenido(
                            evidenciaVideo.id_evidencia,
                          )}
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
                  puedes generar un enlace/QR para que el cliente las capture
                  con su celular.
                </p>
              )}
            </TarjetaColapsable>

            {documentosFirmados.length > 0 && (
              <TarjetaColapsable
                titulo={
                  <>
                    <Download size={18} /> Documentos firmados (legalización)
                  </>
                }
                resumen={`${documentosFirmados.length} documentos`}
                acciones={
                  datos?.id_solicitud ? (
                    <button
                      type="button"
                      onClick={() =>
                        descargarArchivoAutenticado(
                          urlPaqueteLegalizacion(datos.id_solicitud),
                          `legalizacion_${datos.num_solicitud ?? ''}.zip`,
                        )
                      }
                      className="shrink-0 inline-flex items-center gap-1.5 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700 hover:bg-emerald-100"
                    >
                      <Download size={14} /> Descargar todo (.zip)
                    </button>
                  ) : null
                }
              >
                <p className="text-xs text-slate-500 mb-4">
                  Generados al verificar la firma OTP del cliente. Sellados con
                  la fecha y el UUID de firma de la solicitud.
                </p>
                <ul className="divide-y divide-slate-100">
                  {documentosFirmados.map((doc) => (
                    <li
                      key={doc.id_evidencia}
                      className="py-2.5 flex items-center justify-between gap-4"
                    >
                      <span className="text-sm text-slate-700 truncate">
                        {doc.nombre_original ?? doc.tipo}
                      </span>
                      <span className="shrink-0 inline-flex items-center gap-3">
                        <button
                          type="button"
                          onClick={() => setDocPrevia(doc)}
                          className="inline-flex items-center gap-1.5 text-xs font-medium text-sky-700 hover:text-sky-800"
                        >
                          <Eye size={14} /> Ver
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            descargarArchivoAutenticado(
                              urlEvidenciaContenido(doc.id_evidencia),
                              doc.nombre_original ?? undefined,
                            )
                          }
                          className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-700 hover:text-emerald-800"
                        >
                          <Download size={14} /> Descargar
                        </button>
                      </span>
                    </li>
                  ))}
                </ul>
              </TarjetaColapsable>
            )}
          </>
        )}

        {vista === 'evaluacion' && !vistaBinaria && (
          <>
            {evaluacion && (
              <Tarjeta>
                <h3 className="font-semibold mb-4 flex items-center gap-2">
                  <CreditCard size={18} /> Evaluación del motor
                </h3>
                <dl className="grid sm:grid-cols-2 gap-x-8 gap-y-4">
                  <Campo
                    k="Score"
                    v={
                      evaluacion.score != null ? Number(evaluacion.score) : '—'
                    }
                  />
                  <Campo
                    k="Perfil score / ingreso"
                    v={
                      [evaluacion.perfil_score, evaluacion.perfil_ingreso]
                        .filter(Boolean)
                        .join(' · ') || '—'
                    }
                  />
                  <Campo
                    k="Capacidad de pago"
                    v={capacidad != null ? currency(capacidad) : '—'}
                  />
                  <Campo
                    k="Endeudamiento"
                    v={
                      endeudamiento != null
                        ? `${endeudamiento.toFixed(1)}%`
                        : '—'
                    }
                  />
                  <Campo k="Versión evaluación" v={evaluacion.version} />
                  <Campo
                    k="Decisión interna"
                    v={evaluacion.decision_interna ?? '—'}
                    tono={
                      visual === 'APROBADO'
                        ? 'emerald'
                        : visual === 'RECHAZADO'
                          ? 'red'
                          : undefined
                    }
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
                  <dl className="grid sm:grid-cols-2 gap-x-8 gap-y-4">
                    <Campo
                      k="Ingreso final"
                      v={currency(Number(resultadoAuditoria.ingreso_final))}
                    />
                    <Campo
                      k="Fuente del ingreso"
                      v={resultadoAuditoria.fuente_ingreso_final}
                    />
                    <Campo
                      k="Endeudamiento"
                      v={`${Number(resultadoAuditoria.endeudamiento).toFixed(1)}%`}
                    />
                    <Campo
                      k="Disponible"
                      v={currency(Number(resultadoAuditoria.disponible))}
                      tono="emerald"
                    />
                    <Campo
                      k="Capacidad de pago"
                      v={currency(Number(resultadoAuditoria.capacidad_pago))}
                    />
                    <Campo
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
              <TarjetaColapsable
                titulo={
                  <>
                    <Database size={18} /> Detalle de evaluación
                  </>
                }
                resumen="Decisión · buró · parámetros del motor"
              >
                <div className="mb-4">
                  <div
                    className="inline-flex max-w-full flex-wrap bg-slate-100 rounded-full p-1 text-xs"
                    role="group"
                    aria-label="Información de la evaluación"
                  >
                    <button
                      type="button"
                      onClick={() => setJsonTab('resultado')}
                      aria-pressed={jsonTab === 'resultado'}
                      className={`px-3 py-1.5 rounded-full ${jsonTab === 'resultado' ? 'bg-white shadow font-medium' : 'text-slate-500'}`}
                    >
                      Decisión final
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
                  <div className="grid gap-4 xl:grid-cols-2">
                    <SeccionAuditoria titulo="Decisión y perfil">
                      <Campo
                        k="Decisión"
                        v={auditoria.resultado.decision}
                        tono={tonoDecision(auditoria.resultado.decision)}
                      />
                      <Campo
                        k="Decisión interna"
                        v={auditoria.resultado.decision_interna}
                        tono={tonoDecision(
                          auditoria.resultado.decision_interna,
                        )}
                      />
                      <Campo
                        k="Score consultado"
                        v={auditoria.resultado.score_consultado ?? '—'}
                      />
                      <Campo
                        k="Tipo de score"
                        v={auditoria.resultado.score_tipo ?? '—'}
                      />
                      <Campo
                        k="Perfil de score"
                        v={auditoria.resultado.perfil_score ?? '—'}
                      />
                      <Campo
                        k="Perfil de ingreso"
                        v={auditoria.resultado.perfil_ingreso ?? '—'}
                      />
                    </SeccionAuditoria>

                    <SeccionAuditoria titulo="Ingresos y capacidad de pago">
                      <Campo
                        k="Ingreso reportado por la evaluación"
                        v={formatCurrencyValue(
                          auditoria.resultado.valor_ingreso,
                        )}
                      />
                      <Campo
                        k="Estimación de ingreso HDC+ (Quanto)"
                        v={formatCurrencyValue(
                          auditoria.resultado.quanto_medio,
                        )}
                      />
                      <Campo
                        k="Ingreso usado por el motor"
                        v={formatCurrencyValue(
                          auditoria.resultado.ingreso_final,
                        )}
                        tono="emerald"
                      />
                      <Campo
                        k="Fuente del ingreso"
                        v={auditoria.resultado.fuente_ingreso_final}
                      />
                      <Campo
                        k="Ingreso en SMMLV"
                        v={auditoria.resultado.ingreso_final_smmlv}
                      />
                      <Campo
                        k="Gastos personales estimados"
                        v={formatCurrencyValue(
                          auditoria.resultado.gastos_personales,
                        )}
                      />
                      <Campo
                        k="Gastos financieros rotativos"
                        v={formatCurrencyValue(
                          auditoria.resultado.gasto_financiero_rotativo,
                        )}
                      />
                      <Campo
                        k="Gastos financieros no rotativos"
                        v={formatCurrencyValue(
                          auditoria.resultado.gastos_financieros_no_rotativos,
                        )}
                      />
                      <Campo
                        k="Endeudamiento"
                        v={formatPercentageValue(
                          auditoria.resultado.endeudamiento,
                        )}
                      />
                      <Campo
                        k="Disponible"
                        v={formatCurrencyValue(auditoria.resultado.disponible)}
                      />
                      <Campo
                        k="Capacidad de pago"
                        v={formatCurrencyValue(
                          auditoria.resultado.capacidad_pago,
                        )}
                      />
                      <Campo
                        k="Cupo sugerido"
                        v={formatCurrencyValue(
                          auditoria.resultado.cupo_sugerido,
                        )}
                      />
                      <Campo
                        k="Cuota sugerida"
                        v={formatCurrencyValue(
                          auditoria.resultado.cuota_sugerida,
                        )}
                      />
                      <Campo
                        k="Cuota de la moto solicitada"
                        v={formatCurrencyValue(auditoria.resultado.cuota_moto)}
                      />
                    </SeccionAuditoria>

                    <SeccionAuditoria
                      titulo="Indicadores del historial crediticio"
                      columnas="lg:grid-cols-3"
                      className="xl:col-span-2"
                    >
                      {Object.entries(
                        auditoria.resultado.indicadores_buro,
                      ).filter(
                        ([, value]) =>
                          value == null ||
                          ['string', 'number', 'boolean'].includes(
                            typeof value,
                          ),
                      ).length > 0 ? (
                        Object.entries(auditoria.resultado.indicadores_buro)
                          .filter(
                            ([, value]) =>
                              value == null ||
                              ['string', 'number', 'boolean'].includes(
                                typeof value,
                              ),
                          )
                          .map(([key, value]) => (
                            <Campo
                              key={key}
                              k={INDICADOR_LABELS[key] ?? labelReadable(key)}
                              v={formatReadableValue(value)}
                            />
                          ))
                      ) : (
                        <div className="sm:col-span-2 lg:col-span-3">
                          <p className="text-sm text-slate-500">
                            La auditoría no contiene indicadores de historial
                            crediticio para esta evaluación.
                          </p>
                        </div>
                      )}
                    </SeccionAuditoria>

                    {/* Obligaciones reportadas en centrales (cuando la
                    auditoría conserva el detalle del buró) */}
                    {(
                      [
                        'tarjetas_credito',
                        'cuentas_cartera',
                        'endeudamiento_global',
                      ] as const
                    ).map((clave) => {
                      const filas = listaBuro(
                        auditoria.resultado.indicadores_buro,
                        clave,
                      )
                      if (filas.length === 0) return null
                      return (
                        <SeccionAuditoria
                          key={clave}
                          titulo={
                            clave === 'tarjetas_credito'
                              ? 'Tarjetas de crédito y rotativos'
                              : clave === 'cuentas_cartera'
                                ? 'Obligaciones de cartera'
                                : 'Endeudamiento global por entidad'
                          }
                          columnas="1"
                          className="xl:col-span-2"
                        >
                          <div className="overflow-x-auto">
                            <table className="w-full text-xs">
                              <thead>
                                <tr className="border-b border-slate-200 text-left text-slate-500">
                                  <th className="py-2 pr-3 font-medium">
                                    Entidad
                                  </th>
                                  {clave === 'tarjetas_credito' && (
                                    <th className="py-2 pr-3 font-medium">
                                      Franquicia
                                    </th>
                                  )}
                                  {clave === 'cuentas_cartera' && (
                                    <th className="py-2 pr-3 font-medium">
                                      Tipo
                                    </th>
                                  )}
                                  {clave === 'endeudamiento_global' && (
                                    <>
                                      <th className="py-2 pr-3 font-medium">
                                        Sector
                                      </th>
                                      <th className="py-2 pr-3 font-medium">
                                        Tipo crédito
                                      </th>
                                    </>
                                  )}
                                  {clave === 'tarjetas_credito' && (
                                    <th className="py-2 pr-3 font-medium text-right">
                                      Cupo
                                    </th>
                                  )}
                                  <th className="py-2 pr-3 font-medium text-right">
                                    {clave === 'endeudamiento_global'
                                      ? 'Saldo pendiente'
                                      : 'Saldo'}
                                  </th>
                                  {clave !== 'endeudamiento_global' && (
                                    <th className="py-2 pr-3 font-medium text-right">
                                      Cuota
                                    </th>
                                  )}
                                  <th className="py-2 pr-3 font-medium">
                                    {clave === 'endeudamiento_global'
                                      ? 'Créditos'
                                      : 'Estado'}
                                  </th>
                                </tr>
                              </thead>
                              <tbody>
                                {filas.map((fila, i) => (
                                  <tr
                                    key={i}
                                    className="border-b border-slate-100 text-slate-700"
                                  >
                                    <td className="py-2 pr-3 font-medium">
                                      {str(fila.entidad)}
                                    </td>
                                    {clave === 'tarjetas_credito' && (
                                      <td className="py-2 pr-3">
                                        {str(fila.franquicia ?? fila.clase)}
                                      </td>
                                    )}
                                    {clave === 'cuentas_cartera' && (
                                      <td className="py-2 pr-3">
                                        {str(fila.tipo_cuenta)}
                                      </td>
                                    )}
                                    {clave === 'endeudamiento_global' && (
                                      <>
                                        <td className="py-2 pr-3">
                                          {str(fila.sector)}
                                        </td>
                                        <td className="py-2 pr-3">
                                          {str(fila.tipo_credito)}
                                        </td>
                                      </>
                                    )}
                                    {clave === 'tarjetas_credito' && (
                                      <td className="py-2 pr-3 text-right">
                                        {formatCurrencyValue(fila.cupo_total)}
                                      </td>
                                    )}
                                    <td className="py-2 pr-3 text-right">
                                      {formatCurrencyValue(
                                        clave === 'endeudamiento_global'
                                          ? fila.saldo_pendiente
                                          : fila.saldo_actual,
                                      )}
                                    </td>
                                    {clave !== 'endeudamiento_global' && (
                                      <td className="py-2 pr-3 text-right">
                                        {formatCurrencyValue(fila.cuota)}
                                      </td>
                                    )}
                                    <td className="py-2 pr-3">
                                      {clave === 'endeudamiento_global'
                                        ? str(fila.numero_creditos)
                                        : str(
                                            fila.estado_cuenta_desc ??
                                              fila.estado_cuenta ??
                                              fila.estado_pago ??
                                              fila.calificacion_desc ??
                                              fila.calificacion,
                                          )}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </SeccionAuditoria>
                      )
                    })}

                    {/* Alertas del buró (multa/alertas reportadas) */}
                    {listaBuro(auditoria.resultado.indicadores_buro, 'alertas')
                      .length > 0 && (
                      <SeccionAuditoria
                        titulo="Alertas de centrales de riesgo"
                        columnas="1"
                        className="xl:col-span-2"
                      >
                        <ul className="space-y-1.5 text-sm text-slate-700">
                          {listaBuro(
                            auditoria.resultado.indicadores_buro,
                            'alertas',
                          ).map((a, i) => (
                            <li key={i} className="flex gap-2">
                              <span className="font-mono text-xs text-amber-700">
                                {str(a.codigo)}
                              </span>
                              <span>{str(a.texto)}</span>
                              {a.fuente != null && (
                                <span className="text-xs text-slate-500">
                                  ({str(a.fuente)})
                                </span>
                              )}
                            </li>
                          ))}
                        </ul>
                      </SeccionAuditoria>
                    )}

                    {/* Parámetros del motor usados en esta evaluación */}
                    {auditoria.resultado.parametros_usados != null &&
                      Object.keys(auditoria.resultado.parametros_usados)
                        .length > 0 && (
                        <SeccionAuditoria
                          titulo="Parámetros del motor usados"
                          columnas="lg:grid-cols-4"
                          className="xl:col-span-2"
                        >
                          {Object.entries(auditoria.resultado.parametros_usados)
                            .filter(
                              ([, v]) =>
                                v == null ||
                                ['string', 'number', 'boolean'].includes(
                                  typeof v,
                                ),
                            )
                            .map(([k, v]) => (
                              <Campo
                                key={k}
                                k={labelReadable(k)}
                                v={formatReadableValue(v)}
                              />
                            ))}
                        </SeccionAuditoria>
                      )}

                    {auditoria.resultado.advertencias.length > 0 && (
                      <section
                        aria-label="Advertencias"
                        className="rounded-xl border border-amber-200 bg-amber-50/40 p-4 xl:col-span-2"
                      >
                        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-amber-800">
                          Advertencias
                        </h4>
                        <ul className="list-disc space-y-1 pl-5 text-sm text-amber-800">
                          {auditoria.resultado.advertencias.map(
                            (advertencia, index) => (
                              <li key={`${index}-${advertencia}`}>
                                {advertencia}
                              </li>
                            ),
                          )}
                        </ul>
                      </section>
                    )}
                  </div>
                ) : (
                  <SeccionAuditoria
                    titulo="Datos usados para la evaluación"
                    columnas="lg:grid-cols-4"
                  >
                    {Object.entries(auditoria.request).map(([key, value]) => (
                      <Campo
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
                  </SeccionAuditoria>
                )}

                <p className="mt-4 rounded-lg bg-slate-50 p-3 text-xs leading-relaxed text-slate-600">
                  Se muestran los resultados normalizados, las obligaciones del
                  buró y los parámetros usados por el motor en esta evaluación.
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
              </TarjetaColapsable>
            )}
          </>
        )}

        {vista === 'gestion' && (
          <>
            {ofertaElegible && (
              <Tarjeta>
                <h3 className="font-semibold mb-4 flex items-center gap-2">
                  <BadgePercent size={18} />
                  {ofertaSeleccionada
                    ? 'Oferta seleccionada'
                    : 'Oferta elegible'}
                </h3>
                <dl className="grid sm:grid-cols-2 gap-x-8 gap-y-4">
                  <Campo
                    k="Monto aprobado"
                    v={
                      ofertaElegible.monto_aprobado != null
                        ? currency(Number(ofertaElegible.monto_aprobado))
                        : '—'
                    }
                  />
                  <Campo
                    k="Tasa ofrecida"
                    v={
                      ofertaElegible.tasa_ofrecida != null
                        ? `${Number(ofertaElegible.tasa_ofrecida)}% m.v.`
                        : '—'
                    }
                  />
                  <Campo
                    k="Plazo"
                    v={
                      ofertaElegible.plazo_ofrecido != null
                        ? `${ofertaElegible.plazo_ofrecido} meses`
                        : '—'
                    }
                  />
                  <Campo
                    k="Cuota mensual"
                    v={
                      ofertaElegible.cuota_mensual != null
                        ? currency(Number(ofertaElegible.cuota_mensual))
                        : '—'
                    }
                  />
                  <Campo
                    k="Vigencia"
                    v={
                      ofertaElegible.fecha_vigencia
                        ? ofertaElegible.expirada
                          ? `Expirada (${dateShort(ofertaElegible.fecha_vigencia)})`
                          : `Válida hasta ${dateShort(ofertaElegible.fecha_vigencia)}`
                        : '—'
                    }
                    tono={ofertaElegible.expirada ? 'red' : undefined}
                  />
                </dl>
              </Tarjeta>
            )}

            {datos.estado === 'aprobada' &&
              !ofertaSeleccionada &&
              ofertaElegible?.expirada && (
                <Tarjeta className="border-amber-200 bg-amber-50/40">
                  <p className="text-sm text-amber-900">
                    La oferta expiró el{' '}
                    {dateShort(ofertaElegible.fecha_vigencia!)}. Genera una
                    nueva evaluación para emitir una oferta con las condiciones
                    vigentes.
                  </p>
                </Tarjeta>
              )}

            {!vistaBinaria && (datos.consentimientos?.length ?? 0) > 0 && (
              <TarjetaColapsable
                titulo={
                  <>
                    <ShieldCheck size={18} /> Consentimiento Habeas Data
                  </>
                }
                resumen={`${datos.consentimientos!.length} registro${
                  datos.consentimientos!.length === 1 ? '' : 's'
                }`}
              >
                <ul className="space-y-3 text-sm">
                  {datos.consentimientos!.map((c, i) => (
                    <li
                      key={i}
                      className="border border-slate-200 rounded-lg px-4 py-3"
                    >
                      <div className="flex flex-wrap gap-x-6 gap-y-1">
                        <span>
                          <strong>Canal:</strong>{' '}
                          {c.canal === 'otp_firma'
                            ? 'Firma OTP'
                            : 'Web (asesor)'}
                        </span>
                        <span>
                          <strong>Versión:</strong> {c.version_texto}
                        </span>
                        <span>
                          <strong>Fecha y hora:</strong>{' '}
                          {dateTime(c.fecha_aceptacion)}
                        </span>
                        <span>
                          <strong>IP:</strong> {c.ip ?? '—'}
                        </span>
                      </div>
                      <p
                        className="mt-1 text-xs text-slate-500 font-mono"
                        title={c.hash_texto}
                      >
                        sha256: {c.hash_texto.slice(0, 24)}…
                      </p>
                    </li>
                  ))}
                </ul>
              </TarjetaColapsable>
            )}

            {datos.desembolso && (
              <Tarjeta className="border-emerald-200 bg-emerald-50/40">
                <h3 className="font-semibold text-emerald-900 mb-4 flex items-center gap-2">
                  <Landmark size={18} /> Desembolso{' '}
                  {datos.desembolso.num_desembolso ?? ''}
                </h3>
                <dl className="grid sm:grid-cols-2 gap-x-8 gap-y-4">
                  <Campo
                    k="Estado"
                    v={datos.desembolso.estado}
                    tono="emerald"
                  />
                  <Campo
                    k="Capital"
                    v={currency(Number(datos.desembolso.capital))}
                    tono="emerald"
                  />
                  <Campo
                    k="Cuota"
                    v={currency(Number(datos.desembolso.cuota))}
                    tono="emerald"
                  />
                  <Campo
                    k="Tasa / plazo"
                    v={`${Number(datos.desembolso.tasa)}% m.v. · ${datos.desembolso.plazo} meses`}
                    tono="emerald"
                  />
                  <Campo k="Emisor" v={datos.desembolso.emisor} />
                  <Campo k="Receptor" v={datos.desembolso.receptor} />
                  <Campo
                    k="Referencia"
                    v={datos.desembolso.referencia_pago ?? '—'}
                  />
                  <Campo
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
                  El cliente puede tomar un monto menor al cupo aprobado o un
                  plazo más corto del ofertado. La cuota se recalcula con la
                  tasa de la oferta ({Number(ofertaElegible.tasa_ofrecida ?? 0)}
                  % m.v.).
                </p>
                <div className="grid sm:grid-cols-3 gap-3 text-sm">
                  <label className="block">
                    <span className="text-xs uppercase text-slate-500">
                      Monto a tomar (máx.{' '}
                      {currency(Number(ofertaElegible.monto_aprobado ?? 0))})
                    </span>
                    <CampoNumerico
                      className="input-base mt-1 w-full"
                      formatoMiles
                      minimo={0}
                      maximo={Number(ofertaElegible.monto_aprobado ?? 0)}
                      value={montoTomar === '' ? null : Number(montoTomar)}
                      onValor={(n) => setMontoTomar(n == null ? '' : String(n))}
                      placeholder={String(
                        Number(ofertaElegible.monto_aprobado ?? 0),
                      )}
                    />
                  </label>
                  <label className="block">
                    <span className="text-xs uppercase text-slate-500">
                      Plazo (12 a {ofertaElegible.plazo_ofrecido ?? 0} meses)
                    </span>
                    <CampoNumerico
                      className="input-base mt-1 w-full"
                      value={plazoTomar === '' ? null : Number(plazoTomar)}
                      onValor={(n) => setPlazoTomar(n == null ? '' : String(n))}
                      aria-invalid={plazoInvalido}
                      aria-describedby="plazo-tomar-ayuda"
                    />
                  </label>
                  <p id="plazo-tomar-ayuda" className="text-xs text-slate-500">
                    Entre 12 y {ofertaElegible.plazo_ofrecido ?? 0} meses.
                  </p>
                  {plazoInvalido && (
                    <p className="text-xs text-red-600" role="alert">
                      El plazo debe estar entre 12 y{' '}
                      {ofertaElegible.plazo_ofrecido ?? 0} meses.
                    </p>
                  )}
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
          </>
        )}

        {/* Causales: dato sensible, solo visible para el administrador.
            Las vigentes son las de la evaluación actual; las inactivas
            quedaron registradas en evaluaciones anteriores (p. ej. un
            rechazo que el administrador re-evaluó y logró aprobar). */}
        {vista === 'evaluacion' &&
          !vistaBinaria &&
          datos.causales.some((c) => c.activa) && (
            <Tarjeta className="border-amber-200 bg-amber-50/40">
              <h3 className="font-semibold text-amber-900 mb-3 flex items-center gap-2">
                <AlertTriangle size={18} /> Causales de la evaluación vigente
              </h3>
              <ul className="space-y-2">
                {datos.causales
                  .filter((c) => c.activa)
                  .map((c, i) => (
                    <li
                      key={`${c.codigo}-${i}`}
                      className="flex items-start gap-3 rounded-xl border border-amber-200 bg-white/70 px-4 py-3"
                    >
                      <span className="mt-0.5 shrink-0 rounded-md bg-amber-100 px-2 py-0.5 text-xs font-bold tracking-wide text-amber-800">
                        {c.codigo}
                      </span>
                      <span className="text-sm leading-snug text-amber-900">
                        {c.descripcion}
                      </span>
                    </li>
                  ))}
              </ul>
            </Tarjeta>
          )}

        {vista === 'evaluacion' &&
          !vistaBinaria &&
          datos.causales.some((c) => !c.activa) && (
            <TarjetaColapsable
              titulo={
                <>
                  <AlertTriangle size={18} /> Causales de evaluaciones
                  anteriores
                </>
              }
              resumen={`${datos.causales.filter((c) => !c.activa).length} causal${
                datos.causales.filter((c) => !c.activa).length === 1 ? '' : 'es'
              }`}
            >
              <p className="text-xs text-slate-500 mb-3">
                Quedan registradas aunque la evaluación vigente las haya
                superado: son la trazabilidad del rechazo previo.
              </p>
              <ul className="space-y-2">
                {datos.causales
                  .filter((c) => !c.activa)
                  .map((c, i) => (
                    <li
                      key={`hist-${c.codigo}-${i}`}
                      className="flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3"
                    >
                      <span className="mt-0.5 shrink-0 rounded-md bg-slate-200 px-2 py-0.5 text-xs font-bold tracking-wide text-slate-600">
                        {c.codigo}
                      </span>
                      <span className="text-sm leading-snug text-slate-600">
                        {c.descripcion}
                      </span>
                    </li>
                  ))}
              </ul>
            </TarjetaColapsable>
          )}

        {/* Cada re-evaluación crea una versión nueva: el historial deja
            constancia de cuántas hubo y con qué decisión terminaron. */}
        {vista === 'evaluacion' && !vistaBinaria && auditorias.length > 1 && (
          <TarjetaColapsable
            titulo={
              <>
                <History size={18} /> Historial de evaluaciones
              </>
            }
            resumen={`${auditorias.length} versiones`}
          >
            <p className="text-xs text-slate-500 mb-3">
              La evaluación vigente es la primera; las anteriores quedan
              registradas como versiones previas.
            </p>
            <ul className="divide-y divide-slate-100">
              {auditorias.map((a, i) => {
                const tono = tonoDecision(a.decision)
                return (
                  <li
                    key={a.evaluacion_id}
                    className="flex flex-wrap items-center gap-x-4 gap-y-1 py-2.5 text-sm"
                  >
                    <span className="font-medium text-slate-900">
                      Evaluación {auditorias.length - i}
                    </span>
                    <span
                      className={`text-xs font-semibold capitalize ${
                        tono === 'emerald'
                          ? 'text-emerald-700'
                          : tono === 'red'
                            ? 'text-red-700'
                            : 'text-amber-700'
                      }`}
                    >
                      {a.decision}
                      {a.decision_interna && a.decision_interna !== a.decision
                        ? ` · ${a.decision_interna}`
                        : ''}
                    </span>
                    <span className="text-xs text-slate-500">
                      {dateShort(a.fecha_evaluacion)} · {a.origen_datos}
                    </span>
                    {a.causales.length > 0 && (
                      <span className="text-xs text-slate-500">
                        {a.causales.length} causal
                        {a.causales.length === 1 ? '' : 'es'} registrada
                        {a.causales.length === 1 ? '' : 's'}
                      </span>
                    )}
                    {i === 0 && (
                      <span className="ml-auto text-[11px] font-semibold uppercase tracking-wide text-brand-700">
                        Vigente
                      </span>
                    )}
                  </li>
                )
              })}
            </ul>
          </TarjetaColapsable>
        )}

        {vista === 'gestion' && !evaluacion && (
          <Tarjeta className="text-sm text-slate-600">
            <div className="flex flex-wrap items-center gap-3">
              <ListChecks size={18} className="text-slate-400" />
              <span className="flex-1">
                Esta solicitud aún no ha sido evaluada. Puedes lanzar la
                evaluación desde aquí — usa la capacidad referencial calculada
                con el ingreso declarado.
              </span>
              <button
                className="btn-primary"
                onClick={evaluarPendiente}
                disabled={mutEvaluar.isPending}
              >
                {mutEvaluar.isPending ? 'Evaluando…' : 'Evaluar solicitud'}
              </button>
            </div>
            {mutEvaluar.error && (
              <p role="alert" className="mt-3 text-sm text-red-600">
                {mensajeError(mutEvaluar.error, 'Error evaluando la solicitud')}
              </p>
            )}
          </Tarjeta>
        )}

        {/* Re-evaluar con parámetros editables: solo administrador y solo
            en solicitudes rechazadas — sirve para encontrar con qué
            monto, plazo y tasa sí pasaría. */}
        {vista === 'gestion' &&
          !vistaBinaria &&
          evaluacion &&
          /* Retomables: rechazadas por el motor. Cubre también las
             'en_revision' legadas (estado viejo ya no emitido);
             canceladas y desembolsadas son estados finales. */
          datos.decision === 'rechazado' &&
          datos.estado !== 'cancelada' &&
          datos.estado !== 'desembolsada' && (
            <Tarjeta>
              <h3 className="font-semibold mb-1 flex items-center gap-2">
                <ListChecks size={18} /> Re-evaluar con otros parámetros
              </h3>
              <p className="text-xs text-slate-500 mb-4">
                En una solicitud rechazada sirve para asignar el monto, el plazo
                y la tasa con los que sí pasaría. Reusa los datos de buró de la
                evaluación vigente; cada ejecución crea una versión nueva que
                queda registrada en la pestaña Evaluación. Los campos vacíos
                usan los valores vigentes.
              </p>
              {/* Insumos de la evaluación vigente: los mismos valores que
                la calculadora manual de retoma (score, ingreso, gastos →
                capacidad) para que el administrador haga cuentas sin salir
                de la pantalla. */}
              <div className="mb-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                  Valores de la evaluación vigente
                </p>
                <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3 xl:grid-cols-6">
                  <Campo
                    k="Score"
                    v={
                      resultadoAuditoria?.score_consultado ??
                      evaluacion?.score ??
                      '—'
                    }
                  />
                  <Campo
                    k="Ingreso final"
                    v={(() => {
                      const n = numero(resultadoAuditoria?.ingreso_final)
                      return n != null ? currency(n) : '—'
                    })()}
                  />
                  <Campo
                    k="Endeudamiento"
                    v={(() => {
                      const n =
                        numero(resultadoAuditoria?.endeudamiento) ??
                        endeudamiento
                      return n != null ? `${n.toFixed(1)}%` : '—'
                    })()}
                  />
                  <Campo
                    k="Disponible"
                    v={(() => {
                      const n = numero(resultadoAuditoria?.disponible)
                      return n != null ? currency(n) : '—'
                    })()}
                  />
                  <Campo
                    k="Capacidad de pago"
                    tono="emerald"
                    v={
                      reCapacidadPrev != null ? currency(reCapacidadPrev) : '—'
                    }
                  />
                  <Campo
                    k="Cupo vigente"
                    v={currency(Math.round(reSaldoDef))}
                  />
                </dl>
              </div>
              <div className="grid sm:grid-cols-3 gap-3 text-sm">
                <label className="block">
                  <span className="text-xs uppercase text-slate-500">
                    Saldo a financiar
                  </span>
                  <CampoNumerico
                    className="input-base mt-1 w-full"
                    formatoMiles
                    minimo={1}
                    value={reSaldo}
                    onValor={(n) => setReSaldo(n)}
                    placeholder={String(Math.round(reSaldoDef))}
                  />
                </label>
                <label className="block">
                  <span className="text-xs uppercase text-slate-500">
                    Plazo (meses)
                  </span>
                  <CampoNumerico
                    className="input-base mt-1 w-full"
                    minimo={1}
                    value={rePlazo}
                    onValor={(n) => setRePlazo(n)}
                    placeholder={String(rePlazoDef)}
                  />
                </label>
                <label className="block">
                  <span className="text-xs uppercase text-slate-500">
                    Tasa mensual (% m.v.)
                  </span>
                  <CampoNumerico
                    decimales
                    minimo={0}
                    className="input-base mt-1 w-full"
                    value={reTasa === '' ? null : Number(reTasa)}
                    onValor={(n) => setReTasa(n == null ? '' : String(n))}
                    placeholder={String(reTasaDef)}
                  />
                </label>
              </div>
              {reCuotaPrev != null && (
                <div
                  className={`mt-4 flex flex-wrap items-center gap-x-8 gap-y-2 rounded-lg border px-4 py-3 ${
                    reCapacidadPrev != null && reCuotaPrev > reCapacidadPrev
                      ? 'border-amber-200 bg-amber-50/50'
                      : 'border-slate-200 bg-slate-50'
                  }`}
                >
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                      Cuota estimada (con seguro)
                    </p>
                    <p className="text-lg font-bold text-slate-900">
                      {currency(reCuotaPrev)}
                    </p>
                  </div>
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                      Cupo que cabe con este plazo y tasa
                    </p>
                    <p className="text-lg font-bold text-slate-900">
                      {reCupoPosible != null ? currency(reCupoPosible) : '—'}
                    </p>
                    {reCupoTopadoPorCapacidad && (
                      <p className="text-[10px] text-slate-400">
                        la capacidad alcanza más; topa el máximo del producto (
                        {currency(CUPO_MAXIMO)})
                      </p>
                    )}
                  </div>
                  {reCapacidadPrev != null && (
                    <p
                      className={`ml-auto max-w-52 text-xs font-medium leading-snug ${
                        reCuotaPrev <= reCapacidadPrev
                          ? 'text-emerald-700'
                          : 'text-amber-700'
                      }`}
                    >
                      {reCuotaPrev <= reCapacidadPrev
                        ? `Cabe en la capacidad de pago vigente (${currency(reCapacidadPrev)})`
                        : `Supera la capacidad de pago (${currency(reCapacidadPrev)}): bajar el monto o ampliar el plazo`}
                    </p>
                  )}
                </div>
              )}
              {mutEvaluar.error && (
                <p role="alert" className="mt-3 text-sm text-red-600">
                  {mensajeError(
                    mutEvaluar.error,
                    'Error re-evaluando la solicitud',
                  )}
                </p>
              )}
              {mutEvaluar.isSuccess && (
                <p role="status" className="mt-3 text-sm text-emerald-700">
                  Nueva evaluación registrada — la pestaña Evaluación ya muestra
                  la versión vigente.
                </p>
              )}
              <button
                className="btn-primary mt-4"
                disabled={mutEvaluar.isPending}
                onClick={reevaluar}
              >
                {mutEvaluar.isPending
                  ? 'Evaluando…'
                  : 'Ejecutar nueva evaluación'}
              </button>
            </Tarjeta>
          )}

        {/* Cancelar queda de último: es la acción destructiva del ciclo
            y no debería competir con las gestiones operativas. */}
        {vista === 'gestion' &&
          datos.estado !== 'desembolsada' &&
          datos.estado !== 'cancelada' && (
            <Tarjeta className="border-red-200">
              <h3 className="font-semibold mb-1 flex items-center gap-2 text-red-900">
                <XCircle size={18} /> Cancelar solicitud
              </h3>
              <p className="text-xs text-slate-500 mb-3">
                Anula la solicitud y queda registrada en el historial de
                estados. Esta acción no se puede deshacer.
              </p>
              {confirmarCancelacion ? (
                <>
                  <label className="block text-sm mb-3">
                    <span className="text-xs uppercase text-slate-500">
                      Motivo de la cancelación *
                    </span>
                    <textarea
                      className="input-base mt-1 w-full"
                      rows={2}
                      value={motivoCancelar}
                      onChange={(e) => setMotivoCancelar(e.target.value)}
                      placeholder="Ej: el cliente desistió del crédito"
                    />
                  </label>
                  {mutCancelar.error && (
                    <p role="alert" className="mb-3 text-sm text-red-600">
                      {mensajeError(
                        mutCancelar.error,
                        'No se pudo cancelar la solicitud',
                      )}
                    </p>
                  )}
                  <div className="flex gap-3">
                    <button
                      className="btn-primary !bg-red-600 hover:!bg-red-700"
                      disabled={
                        mutCancelar.isPending ||
                        motivoCancelar.trim().length < 3
                      }
                      onClick={() => mutCancelar.mutate(motivoCancelar.trim())}
                    >
                      {mutCancelar.isPending
                        ? 'Cancelando…'
                        : 'Sí, cancelar la solicitud'}
                    </button>
                    <button
                      className="btn-ghost"
                      onClick={() => setConfirmarCancelacion(false)}
                    >
                      Volver
                    </button>
                  </div>
                </>
              ) : (
                <button
                  className="btn-ghost !text-red-700 !border-red-300 hover:!bg-red-50"
                  onClick={() => setConfirmarCancelacion(true)}
                >
                  Cancelar esta solicitud
                </button>
              )}
            </Tarjeta>
          )}
      </div>
      {docPrevia && (
        <VisorDocumento
          url={urlEvidenciaContenido(docPrevia.id_evidencia)}
          nombre={docPrevia.nombre_original ?? docPrevia.tipo}
          onCerrar={() => setDocPrevia(null)}
        />
      )}
    </>
  )
}

function tonoDecision(valor: unknown): 'emerald' | 'red' | 'amber' | undefined {
  const v = String(valor ?? '').toLowerCase()
  if (v.includes('aprobad')) return 'emerald'
  if (v.includes('rechaz')) return 'red'
  if (v.trim() !== '') return 'amber'
  return undefined
}

/** Sub-tarjeta del detalle de auditoría: agrupa campos con aire visual. */
function SeccionAuditoria({
  titulo,
  children,
  columnas = 'lg:grid-cols-3',
  className = '',
}: {
  titulo: string
  children: ReactNode
  columnas?: string
  className?: string
}) {
  return (
    <section
      aria-label={titulo}
      className={`rounded-xl border border-slate-200 bg-slate-50/40 p-4 ${className}`}
    >
      <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-600">
        {titulo}
      </h4>
      <dl
        className={`grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2 ${columnas}`}
      >
        {children}
      </dl>
    </section>
  )
}

/** Campo apilado (label encima del valor): más legible que label|valor en línea. */
function Campo({
  k,
  v,
  tono,
}: {
  k: string
  v: ReactNode
  tono?: 'emerald' | 'red' | 'amber'
}) {
  const color =
    tono === 'emerald'
      ? 'text-emerald-700'
      : tono === 'red'
        ? 'text-red-700'
        : tono === 'amber'
          ? 'text-amber-700'
          : 'text-slate-900'
  return (
    <div className="min-w-0">
      <dt className="text-[11px] font-medium uppercase tracking-wide text-slate-500">
        {k}
      </dt>
      <dd
        className={`mt-0.5 text-sm font-semibold tabular-nums ${color}`}
        title={typeof v === 'string' ? v : undefined}
      >
        {v}
      </dd>
    </div>
  )
}

function TabDetalle({
  activo,
  onClick,
  children,
}: {
  activo: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={activo}
      onClick={onClick}
      className={`-mb-px border-b-2 px-4 py-2.5 text-sm font-medium transition ${
        activo
          ? 'border-brand-600 text-brand-700'
          : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-800'
      }`}
    >
      {children}
    </button>
  )
}

function EvidenciaImagen({ titulo, url }: { titulo: string; url: string }) {
  const objUrl = useUrlObjetoAutenticado(url)
  return (
    <div className="space-y-2">
      <p className="text-xs uppercase text-slate-500 font-medium">{titulo}</p>
      <div className="group relative rounded-xl overflow-hidden border border-slate-200 bg-slate-50">
        {objUrl ? (
          <>
            <img
              src={objUrl}
              alt={titulo}
              className="w-full h-48 object-cover"
            />
            <a
              href={objUrl}
              target="_blank"
              rel="noreferrer"
              className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center text-white text-sm gap-2 transition"
            >
              <Eye size={16} /> Ver ampliado
            </a>
          </>
        ) : (
          <div className="h-48 animate-pulse bg-slate-100" aria-hidden />
        )}
      </div>
    </div>
  )
}

function EvidenciaVideo({ url }: { url: string }) {
  const objUrl = useUrlObjetoAutenticado(url)
  return objUrl ? (
    <video controls className="w-full h-48 object-cover" src={objUrl} />
  ) : (
    <div className="h-48 animate-pulse bg-slate-800" aria-hidden />
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

/** Lista de objetos dentro de indicadores_buro (cuentas, tarjetas…). */
function listaBuro(
  indicadores: Record<string, unknown>,
  clave: string,
): Record<string, unknown>[] {
  const valor = indicadores[clave]
  return Array.isArray(valor)
    ? valor.filter(
        (v): v is Record<string, unknown> =>
          v != null && typeof v === 'object' && !Array.isArray(v),
      )
    : []
}

/** Texto corto de un valor del buró ('—' cuando viene vacío). */
function str(valor: unknown): string {
  if (valor == null || valor === '') return '—'
  return String(valor)
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
