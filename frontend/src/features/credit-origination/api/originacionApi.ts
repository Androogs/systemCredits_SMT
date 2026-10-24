/**
 * Cliente HTTP del flujo de originación contra la API integrada
 * (POST /api/solicitudes + /evaluar + /ofertas del backend FastAPI).
 */

import { env } from '../../../env'
import { fetchAutenticado } from '../../../shared/lib/fetchAutenticado'

const API = env.VITE_API_URL.replace(/\/$/, '')

// ---------- Tipos espejo del backend ----------

export interface CrearSolicitudResponse {
  id_solicitud: string
  num_solicitud: number | null
  estado: string
}

export interface CausalEvaluacionApi {
  codigo: string
  descripcion: string
}

export interface PasoTrazaApi {
  etapa: string
  resultado: string
  causales: string[]
  detalle: string[]
}

export interface ResultadoMotorApi {
  evaluacion_id: string
  decision: 'Aprobado' | 'Rechazado'
  /** También binaria (D185); 'Estudio' y 'Requiere Codeudor' solo
   * llegan en evaluaciones históricas. */
  decision_interna: 'Aprobado' | 'Rechazado' | 'Estudio' | 'Requiere Codeudor'
  causales: CausalEvaluacionApi[]
  score_consultado: string | null
  score_tipo: string | null
  perfil_score: 'A' | 'B' | 'C' | 'D' | null
  perfil_ingreso: 'ALTO' | 'MEDIO' | 'BAJO' | 'GRIS' | null
  quanto_medio: string
  valor_ingreso: string
  ingreso_final: string
  fuente_ingreso_final: string
  ingreso_final_smmlv: string
  endeudamiento: string
  disponible: string
  capacidad_pago: string
  cupo_sugerido: string
  cuota_sugerida: string
  /** Cuota de la moto con el saldo/tasa/plazo de la solicitud. */
  cuota_moto: string
  /** Cuotas de créditos rotativos reportados en buró (tarjetas, rotativos). */
  gasto_financiero_rotativo: string
  /** Cuotas de obligaciones no rotativas reportadas en buró. */
  gastos_financieros_no_rotativos: string
  /** Gastos personales estimados por banda de SMMLV. */
  gastos_personales: string
  indicadores_buro: Record<string, unknown>
  /** Parámetros del motor usados en esta evaluación (solo en auditoría). */
  parametros_usados?: Record<string, unknown>
  trazabilidad: PasoTrazaApi[]
  advertencias: string[]
  tiempo_ms: number
}

/** Vista operativa del resultado: lo que recibe el asesor y el aliado.
 * El backend omite score, causales e indicadores de buró a roles sin
 * acceso al expediente interno. */
export interface ResultadoBinarioApi {
  evaluacion_id: string
  decision: 'Aprobado' | 'Rechazado'
  cupo_sugerido: string
  cuota_sugerida: string
  cuota_moto: string
  advertencias: string[]
  tiempo_ms: number
}

export type ResultadoEvaluacionApi = ResultadoMotorApi | ResultadoBinarioApi

/** Type guard: la respuesta trae expediente interno (rol admin). */
export function esResultadoInterno(
  resultado: ResultadoEvaluacionApi,
): resultado is ResultadoMotorApi {
  return 'decision_interna' in resultado
}

export interface OfertaApi {
  id_oferta: number
  id_aliado_producto: number
  elegible: boolean
  motivo_no_elegible: string | null
  seleccionada: boolean
  tasa_ofrecida: string | null
  plazo_ofrecido: number | null
  cuota_mensual: string | null
  monto_aprobado: string | null
  fecha_vigencia: string | null
  expirada: boolean
}

export interface CrearSolicitudPayload {
  cliente: {
    tipo_documento: string
    num_cedula: string
    nombre_completo: string
    primer_apellido: string
    fecha_nacimiento: string
    ocupacion: string
    nacionalidad: string
    /** Datos de la cédula (paso 3): documentos de legalización. */
    fecha_expedicion?: string | null
    ciudad_expedicion?: string | null
    ciudad_nacimiento?: string | null
  }
  datos_laborales: {
    tipo_contrato: string | null
    meses_continuidad: number | null
    ingreso_mensual: number
    otros_ingresos: number
    anios_camara_comercio: number | null
    /** Empleador/entidad pagadora del paso 4: precarga la formalización. */
    nombre_empresa?: string | null
  }
  contacto_vivienda: {
    estrato?: number | null
    personas_a_cargo?: number | null
    tipo_vivienda?: string | null
    correo?: string | null
    telefono?: string | null
  }
  linea_credito?: string
  destino_credito?: string
  plazo_deseado_meses?: number
  /** Solo para el concesionario: radica a nombre de un asesor de su
      sede (obligatorio en ese rol; el asesor radica a su nombre). */
  id_asesor?: number
  /** Aceptación Habeas Data del paso 2: el backend sella versión y hash. */
  consentimiento?: { aceptado: boolean }
  /** Token del link de captura (paso 3): enlaza las evidencias del cliente. */
  sesion_captura?: string
}

export interface EvaluarSolicitudPayload {
  saldo_financiar: number
  plazo: number
  tasa: number
  primer_apellido?: string
  tiene_multas_runt?: boolean
  consultar_experian?: boolean
  escenario_mock?: string | null
}

export class ApiError extends Error {
  readonly status: number
  readonly detalle: unknown

  constructor(status: number, detalle: unknown) {
    super(typeof detalle === 'string' ? detalle : `Error HTTP ${status}`)
    this.status = status
    this.detalle = detalle
  }
}

interface OpcionesRequest extends RequestInit {
  /** Timeout por intento en ms (default 30s). */
  timeoutMs?: number
  /** Reintentos extra en fallos de red o 5xx (default: 2 para GET, 0 para el resto). */
  reintentos?: number
}

const TIMEOUT_POR_DEFECTO_MS = 30_000
const ESPERA_REINTENTO_MS = 400

function esperar(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function request<T>(ruta: string, init?: OpcionesRequest): Promise<T> {
  const {
    timeoutMs = TIMEOUT_POR_DEFECTO_MS,
    reintentos,
    ...resto
  } = init ?? {}
  const esGet = (resto.method ?? 'GET') === 'GET'
  // Los POST nunca se reintentan automáticamente: crear/evaluar/seleccionar/
  // desembolsar no son idempotentes desde el punto de vista del cliente.
  const intentos = 1 + (reintentos ?? (esGet ? 2 : 0))
  let ultimoError: Error | null = null

  for (let intento = 1; intento <= intentos; intento++) {
    try {
      const respuesta = await fetchAutenticado(`${API}${ruta}`, {
        headers: { 'Content-Type': 'application/json' },
        signal: AbortSignal.timeout(timeoutMs),
        ...resto,
      })
      const cuerpo = await respuesta.json().catch(() => null)
      // El helper ya rotó el refresh ante el 401 (o limpió la sesión y
      // redirigió al login si ni con refresh el servidor la acepta).
      if (respuesta.ok) return cuerpo as T
      const detalleBase =
        cuerpo && typeof cuerpo === 'object'
          ? ((cuerpo as Record<string, unknown>).detail ??
            (cuerpo as Record<string, unknown>).error ??
            cuerpo)
          : null
      // 502 del proxy de Vite (backend apagado o puerto distinto): el cuerpo
      // no es JSON y el genérico "Error HTTP 502" no dice qué hacer.
      const detalle =
        detalleBase ??
        (respuesta.status === 502
          ? 'El proxy de desarrollo devolvió 502: el backend no respondió. ' +
            'Verifica que uvicorn esté corriendo en http://127.0.0.1:8000 y que ' +
            'API_PROXY_TARGET apunte a ese puerto.'
          : `Error HTTP ${respuesta.status}`)
      if (respuesta.status >= 500 && intento < intentos) {
        await esperar(ESPERA_REINTENTO_MS * intento)
        continue
      }
      throw new ApiError(respuesta.status, detalle)
    } catch (e) {
      if (e instanceof ApiError) throw e
      ultimoError = e instanceof Error ? e : new Error(String(e))
      if (intento < intentos) {
        await esperar(ESPERA_REINTENTO_MS * intento)
        continue
      }
    }
  }
  const esTimeout = ultimoError?.name === 'TimeoutError'
  throw new ApiError(
    0,
    esTimeout
      ? `El servidor no respondió en ${Math.round(timeoutMs / 1000)}s. Reintenta.`
      : 'No fue posible contactar el servidor. Verifica tu conexión.',
  )
}

export function crearSolicitud(payload: CrearSolicitudPayload) {
  return request<CrearSolicitudResponse>('/api/solicitudes', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/** Re-diligencia la radicación al retomar pasos pendientes (upsert; el
 * backend responde 409 si la solicitud ya tiene decisión). */
export function actualizarSolicitud(
  idSolicitud: string,
  payload: CrearSolicitudPayload,
) {
  return request<CrearSolicitudResponse>(`/api/solicitudes/${idSolicitud}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function evaluarSolicitud(
  idSolicitud: string,
  payload: EvaluarSolicitudPayload,
) {
  return request<ResultadoEvaluacionApi>(
    `/api/solicitudes/${idSolicitud}/evaluar`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
      // La evaluación consulta Experian en línea (token + HDC+ + Valor
      // Ingreso + motor); puede tardar más que el default de 30s.
      timeoutMs: 120_000,
    },
  )
}

export function obtenerOfertas(idSolicitud: string) {
  return request<OfertaApi[]>(`/api/solicitudes/${idSolicitud}/ofertas`)
}

/** Vehículo que financia el crédito, capturado al aceptar la oferta. */
export interface VehiculoFinanciado {
  producto_a_financiar?: string
  marca?: string | null
  referencia?: string | null
  modelo?: string | null
  color?: string | null
  valor_moto_iva?: number | null
  descuento?: number | null
  descuento_pct?: number | null
  accesorios?: number | null
  matricula?: number | null
  soat?: number | null
  /** Impuesto por cilindraje de la motocicleta (impuesto de registro). */
  impuestos?: number | null
  aval_pct?: number | null
}

export function seleccionarOferta(
  idSolicitud: string,
  idOferta: number,
  monto?: number,
  plazo?: number,
  vehiculo?: VehiculoFinanciado,
) {
  return request<OfertaApi>(
    `/api/solicitudes/${idSolicitud}/ofertas/seleccionar`,
    {
      method: 'POST',
      body: JSON.stringify({
        id_oferta: idOferta,
        ...(monto != null ? { monto } : {}),
        ...(plazo != null ? { plazo } : {}),
        ...(vehiculo != null ? { vehiculo } : {}),
      }),
    },
  )
}

// ---------- Datos del cliente en formalización ----------

/** Información adicional capturada tras los datos del vehículo y antes de
 * enviar el OTP. La dirección viaja descompuesta; el backend la compone. */
export interface DatosFormalizacionPayload {
  via_principal?: string | null
  numero_via?: string | null
  letra_via?: string | null
  sector?: string | null
  numero_cruce?: string | null
  letra_cruce?: string | null
  numero_final?: string | null
  otras_caracteristicas?: string | null
  barrio?: string | null
  ciudad?: string | null
  estrato?: number | null
  tipo_vivienda?: string | null
  zona_rural?: boolean | null
  estado_civil?: string | null
  personas_a_cargo?: number | null
  num_hijos?: number | null
  es_cabeza_familia?: boolean | null
  cuenta_bienes_raices?: boolean | null
  cuenta_vehiculo?: boolean | null
  tiene_moto?: boolean | null
  tiene_carro?: boolean | null
  primera_moto?: boolean | null
  estoy_financiando?: boolean | null
  nombre_empresa?: string | null
  ciudad_empresa?: string | null
  fecha_ingreso?: string | null
  nivel_educativo?: string | null
  profesion?: string | null
  cargo?: string | null
  actividad_comercial?: string | null
}

export function guardarDatosFormalizacion(
  idSolicitud: string,
  payload: DatosFormalizacionPayload,
) {
  return request<void>(`/api/solicitudes/${idSolicitud}/datos-formalizacion`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

// ---------- OTP (firma del pagaré) ----------

export interface GenerarOtpResponse {
  id_otp: number
  expira_en_segundos: number
  /** Canal por el que salió el código ('whatsapp' cae a 'email' cuando
   * no hay teléfono válido o el envío por WATI falla). */
  canal: 'whatsapp' | 'email'
  destino: string | null
  estado_envio: string
  /** Solo en modo demo: el código se muestra en pantalla. */
  codigo_demo: string | null
}

export function generarOtp(idSolicitud: string, accion = 'firma_pagare') {
  return request<GenerarOtpResponse>(`/api/solicitudes/${idSolicitud}/otp`, {
    method: 'POST',
    body: JSON.stringify({ accion, canal: 'whatsapp' }),
  })
}

export function verificarOtp(
  idSolicitud: string,
  codigo: string,
  accion = 'firma_pagare',
) {
  return request<{ verificado: boolean; uuid_firma: string | null }>(
    `/api/solicitudes/${idSolicitud}/otp/verificar`,
    {
      method: 'POST',
      body: JSON.stringify({ accion, codigo }),
    },
  )
}

export function listarEscenariosMock() {
  return request<Record<string, string>>('/api/motor/escenarios')
}

// ---------- Auditoría de evaluaciones ----------

export interface AuditoriaResumenApi {
  evaluacion_id: string
  fecha_evaluacion: string
  origen_datos: string
  id_solicitud: string | null
  numero_id: string
  ocupacion: string
  edad: number
  decision: string
  decision_interna: string
  causales: Record<string, unknown>[]
  tiempo_ms: number
}

export interface AuditoriaDetalleApi extends AuditoriaResumenApi {
  ambiente: string
  request: Record<string, unknown>
  resultado: ResultadoMotorApi
}

export function listarAuditoriaSolicitud(idSolicitud: string) {
  return request<AuditoriaResumenApi[]>(
    `/api/auditoria?id_solicitud=${encodeURIComponent(idSolicitud)}`,
  )
}

export function obtenerAuditoria(evaluacionId: string) {
  return request<AuditoriaDetalleApi>(`/api/auditoria/${evaluacionId}`)
}

// ---------- Consulta de solicitudes persistidas (panel del asesor) ----------

export interface EvaluacionResumenApi {
  id_evaluacion: number
  version: number
  score: string | null
  perfil_score: string | null
  perfil_ingreso: string | null
  decision_interna: string | null
  endeudamiento: string | null
  capacidad_pago: string | null
  cupo_sugerido: string | null
  plazo_cupo: number | null
}

export interface SolicitudResumenApi {
  id_solicitud: string
  num_solicitud: number | null
  fecha_hora: string
  estado: string
  descripcion_estado?: string | null
  decision: string | null
  nombre_cliente: string
  num_cedula: string
  /** Quién radicó y desde qué sede: base del reporte de comisiones
      del aliado; el asesor ve siempre su propio nombre. */
  nombre_asesor?: string | null
  nombre_concesionario?: string | null
  tipo_documento: string | null
  ocupacion: string | null
  linea_credito: string | null
  destino_credito: string | null
  plazo_deseado_meses: number | null
  fecha_hora_firma?: string | null
  evaluacion: EvaluacionResumenApi | null
}

export interface CausalSolicitudApi {
  codigo: string
  descripcion: string
  activa: boolean
}

export interface SolicitudDetalleApi extends SolicitudResumenApi {
  /** Requerida por el payload de re-diligencia al retomar la solicitud. */
  fecha_nacimiento?: string | null
  datos_laborales: {
    tipo_contrato: string | null
    meses_continuidad: number | null
    ingreso_mensual: string | null
    otros_ingresos: string | null
    anios_camara_comercio: string | null
    nombre_empresa?: string | null
    ciudad_empresa?: string | null
    fecha_ingreso?: string | null
    nivel_educativo?: string | null
    profesion?: string | null
    cargo?: string | null
    actividad_comercial?: string | null
  } | null
  contacto_vivienda: {
    estrato: number | null
    personas_a_cargo: number | null
    tipo_vivienda: string | null
    correo?: string | null
    telefono?: string | null
    direccion?: string | null
    barrio?: string | null
    ciudad?: string | null
    zona_rural?: boolean | null
    estado_civil?: string | null
    num_hijos?: number | null
    es_cabeza_familia?: boolean | null
    cuenta_bienes_raices?: boolean | null
    cuenta_vehiculo?: boolean | null
    tiene_moto?: boolean | null
    tiene_carro?: boolean | null
    primera_moto?: boolean | null
    estoy_financiando?: boolean | null
  } | null
  causales: CausalSolicitudApi[]
  ofertas: OfertaApi[]
  desembolso: DesembolsoApi | null
  consentimientos?: ConsentimientoApi[]
}

/** Registro de una aceptación Habeas Data (Ley 1581). */
export interface ConsentimientoApi {
  version_texto: string
  hash_texto: string
  canal: string
  ip: string | null
  fecha_aceptacion: string
}

export interface FiltrosSolicitudes {
  estado?: string
  decision?: string
  busqueda?: string
  limite?: number
  offset?: number
  /** Filtros dimensionales del panel (admin; intersectan el alcance). */
  id_concesionario?: number
  id_asesor?: number
  /** 'prioridad' pone pendientes de evaluación primero (server-side). */
  orden?: 'reciente' | 'prioridad'
}

export function listarSolicitudes(filtros: FiltrosSolicitudes = {}) {
  const params = new URLSearchParams()
  for (const [clave, valor] of Object.entries(filtros)) {
    if (valor !== undefined && valor !== null && valor !== '') {
      params.set(clave, String(valor))
    }
  }
  const qs = params.toString()
  return request<SolicitudResumenApi[]>(`/api/solicitudes${qs ? `?${qs}` : ''}`)
}

export function obtenerSolicitud(idSolicitud: string) {
  return request<SolicitudDetalleApi>(`/api/solicitudes/${idSolicitud}`)
}

// ---------- Métricas del embudo ----------

export interface EtapaEmbudoApi {
  clave: string
  etiqueta: string
  total: number
  pct: number
}

export interface EmbudoAliadoApi {
  aliado: string
  con_oferta: number
  formalizadas: number
  desembolsadas: number
  valor_desembolsado: string
}

export interface EmbudoAsesorApi {
  asesor: string
  cedula: string | null
  titular_anterior: boolean
  radicadas: number
  aprobadas: number
  formalizadas: number
  desembolsadas: number
}

export interface EmbudoCausalApi {
  codigo: string
  descripcion: string
  total: number
}

export interface EmbudoReevaluacionApi {
  reevaluadas: number
  rescatadas: number
}

export interface MetricasEmbudoApi {
  generado_en: string
  radicadas: number
  canceladas: number
  etapas: EtapaEmbudoApi[]
  por_estado: Record<string, number>
  por_aliado: EmbudoAliadoApi[]
  por_asesor: EmbudoAsesorApi[]
  por_causal: EmbudoCausalApi[]
  reevaluacion: EmbudoReevaluacionApi
}

/** Catálogos de los filtros dimensionales del panel, acotados al
    alcance del usuario: aliado → sus sedes y sus asesores, asesor →
    solo él mismo, admin → todo. */
export interface OpcionesFiltroApi {
  concesionarios: { id_concesionario: number; nombre: string }[]
  asesores: {
    id_asesor: number
    nombre: string
    id_concesionario: number | null
  }[]
}

export function obtenerOpcionesFiltro() {
  return request<OpcionesFiltroApi>('/api/catalogos/opciones-filtro')
}

/** Conversión del embudo originación → desembolso (agregados en el
    servidor; no depende del límite de la lista). `desde`/`hasta`
    acotan por fecha de radicación (filtro de mes del panel);
    `id_concesionario`/`id_asesor` son los filtros dimensionales. */
export function obtenerMetricasEmbudo(filtros?: {
  desde?: string
  hasta?: string
  id_concesionario?: number
  id_asesor?: number
}) {
  const params = new URLSearchParams()
  if (filtros?.desde) params.set('desde', filtros.desde)
  if (filtros?.hasta) params.set('hasta', filtros.hasta)
  if (filtros?.id_concesionario)
    params.set('id_concesionario', String(filtros.id_concesionario))
  if (filtros?.id_asesor) params.set('id_asesor', String(filtros.id_asesor))
  const qs = params.toString()
  return request<MetricasEmbudoApi>(
    `/api/solicitudes/metricas/embudo${qs ? `?${qs}` : ''}`,
  )
}

/** Anula la solicitud con motivo; 409 si ya está desembolsada/cancelada. */
export function cancelarSolicitud(idSolicitud: string, motivo: string) {
  return request<SolicitudResumenApi>(
    `/api/solicitudes/${idSolicitud}/cancelar`,
    { method: 'POST', body: JSON.stringify({ motivo }) },
  )
}

// ---------- Catálogo de productos ----------

export interface ProductoApi {
  id_aliado_producto: number
  id_aliado: number
  nombre: string
  aliado: string
  tasa_min: string | null
  tasa_max: string | null
  plazo_min_meses: number | null
  plazo_max_meses: number | null
  monto_min: string | null
  monto_max: string | null
}

export function listarProductos() {
  return request<ProductoApi[]>('/api/productos')
}

// ---------- Tasa de mercado (TIBC SFC) ----------

export interface TasaModalidadApi {
  modalidad: string
  tasa_ea: number
  tasa_mv: number
  usura_ea: number
  usura_mv: number
  vigencia_desde: string
  vigencia_hasta: string
  resolucion: string
}

export interface TasaMercadoApi {
  /** Tope de "consumo bajo monto" en COP (6 SMMLV). */
  umbral_bajo_monto: number
  fuente: string
  bajo_monto: TasaModalidadApi
  ordinario: TasaModalidadApi
}

export function tasaMercado() {
  return request<TasaMercadoApi>('/api/tasa-mercado')
}

export interface DesembolsoApi {
  id_desembolso: number
  num_desembolso: string | null
  id_credito: number
  estado: string
  capital: string
  cuota: string
  plazo: number
  tasa: string
  emisor: string
  receptor: string
  referencia_pago: string | null
  fecha_desembolso: string | null
}

// ---------- Captura remota de evidencias (cédula + video) ----------

export type TipoEvidencia =
  'cedula_frontal' | 'cedula_reverso' | 'video_prueba_vida'

export interface SesionCapturaApi {
  id_sesion: string
  token: string
  estado: 'pendiente' | 'completada' | 'expirada'
  expira_en: string
}

/** Datos del paso 1 contra los que se compara el OCR de la cédula. */
export interface DatosEsperadosOCR {
  nombres?: string
  apellidos?: string
  numero_documento?: string
  fecha_nacimiento?: string
}

/** De dónde salió un campo: MRZ del reverso blanco, anverso, reverso o línea al pie de la amarilla. */
export type FuenteOCR = 'mrz' | 'anverso' | 'reverso' | 'codigo_reverso' | ''

/** Un campo extraído por el OCR, con su confianza (0-100). */
export interface CampoOCRApi {
  valor: string
  confianza: number
  fuente?: FuenteOCR
}

/** Resultado del OCR de la cédula, fusionado de anverso + reverso (paso 3). */
export interface ResultadoOCRApi {
  disponible: boolean
  texto_crudo: string
  /** Diseño detectado: blanca (digital, con MRZ) o amarilla (hologramas). */
  tipo_cedula?: 'blanca' | 'amarilla' | ''
  numero_documento: CampoOCRApi
  nombres: CampoOCRApi
  apellidos: CampoOCRApi
  fecha_nacimiento: CampoOCRApi
  fecha_expedicion: CampoOCRApi
  /** Solo la cédula blanca la trae. */
  fecha_expiracion?: CampoOCRApi
  sexo?: CampoOCRApi
  lugar_nacimiento?: CampoOCRApi
  ciudad_expedicion?: CampoOCRApi
  /** Diferencias a revisar (vs. paso 1, entre caras, cédula vencida). */
  advertencias: string[]
  /** Notas de calidad de la captura; no afectan `coincide`. */
  observaciones?: string[]
  /** true cuando no hay advertencias. */
  coincide: boolean
  /** Lectura cruda por foto (diagnóstico). */
  lecturas?: Record<string, unknown>
}

export interface EvidenciaApi {
  id_evidencia: number
  /** cedula_frontal | cedula_reverso | video_prueba_vida | doc_* (legalización) */
  tipo: string
  nombre_original: string | null
  mime: string
  tamano_bytes: number
  hash_sha256: string
  creado_en: string
}

/**
 * Estado para la página móvil pública. No trae el OCR (datos personales):
 * solo si la cédula se reconoció en cada foto, para pedir repetirla.
 */
export interface EstadoCapturaApi {
  estado: string
  pendientes: TipoEvidencia[]
  evidencias: EvidenciaApi[]
  cedula_legible?: Partial<Record<'cedula_frontal' | 'cedula_reverso', boolean>>
}

/** Estado para el asesor (polling): incluye el OCR fusionado. */
export interface EstadoSesionApi {
  id_sesion: string
  estado: string
  expira_en: string
  pendientes: TipoEvidencia[]
  evidencias: EvidenciaApi[]
  /** Resultado del OCR de la cédula; null hasta que se sube una cara. */
  ocr?: ResultadoOCRApi | null
}

/** El asesor crea la sesión; el token va en el link/QR del celular. */
export function crearSesionCaptura(datosEsperados?: DatosEsperadosOCR) {
  return request<SesionCapturaApi>('/api/sesiones-captura', {
    method: 'POST',
    body: JSON.stringify(datosEsperados ?? {}),
  })
}

/** Polling del asesor: evidencias recibidas en la sesión. */
export function estadoSesionCaptura(idSesion: string) {
  return request<EstadoSesionApi>(`/api/sesiones-captura/${idSesion}`)
}

/** Evidencias ya enlazadas a una solicitud persistida. */
export function listarEvidenciasSolicitud(idSolicitud: string) {
  return request<EvidenciaApi[]>(`/api/solicitudes/${idSolicitud}/evidencias`)
}

/** URL del contenido binario de una evidencia (asesor autenticado). */
export function urlEvidenciaContenido(idEvidencia: number) {
  return `${API}/api/evidencias/${idEvidencia}/contenido`
}

/** URL del paquete completo de legalización (.zip con los doc_*). */
export function urlPaqueteLegalizacion(idSolicitud: string) {
  return `${API}/api/solicitudes/${idSolicitud}/legalizacion.zip`
}

/** Estado para la página móvil pública (autoriza el token del link). */
export function estadoCaptura(token: string) {
  return request<EstadoCapturaApi>(`/api/captura/${token}`)
}

/** Verificación pública de la firma electrónica — destino del QR que se
 * estampa en los documentos de legalización. */
export interface VerificacionFirmaApi {
  uuid_firma: string
  num_solicitud: number | null
  firmante: string
  documento_identidad: string
  fecha_hora_firma: string | null
  autenticacion: string | null
  documentos: number
}

export function verificarFirma(uuidFirma: string) {
  return request<VerificacionFirmaApi>(`/api/firmas/${uuidFirma}`)
}

export function subirEvidencia(
  token: string,
  tipo: TipoEvidencia,
  archivo: Blob,
  nombre: string,
) {
  const form = new FormData()
  form.append('tipo', tipo)
  form.append('archivo', archivo, nombre)
  // multipart: el boundary lo pone el navegador; no fijar Content-Type.
  // El OCR corre en la subida (3-10 s por foto): timeout holgado.
  return request<EvidenciaApi>(`/api/captura/${token}/evidencias`, {
    method: 'POST',
    headers: {},
    body: form,
    timeoutMs: 90_000,
  })
}
