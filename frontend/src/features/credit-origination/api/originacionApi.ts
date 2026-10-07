/**
 * Cliente HTTP del flujo de originación contra la API integrada
 * (POST /api/solicitudes + /evaluar + /ofertas del backend FastAPI).
 */

import { env } from '../../../env'

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
  indicadores_buro: Record<string, unknown>
  trazabilidad: PasoTrazaApi[]
  advertencias: string[]
  tiempo_ms: number
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
  }
  datos_laborales: {
    tipo_contrato: string | null
    meses_continuidad: number | null
    ingreso_mensual: number
    otros_ingresos: number
    anios_camara_comercio: number | null
  }
  contacto_vivienda: Record<string, never>
  linea_credito?: string
  destino_credito?: string
  plazo_deseado_meses?: number
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

async function request<T>(ruta: string, init?: RequestInit): Promise<T> {
  const respuesta = await fetch(`${API}${ruta}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  const cuerpo = await respuesta.json().catch(() => null)
  if (!respuesta.ok) {
    const detalle =
      cuerpo && typeof cuerpo === 'object'
        ? ((cuerpo as Record<string, unknown>).detail ??
          (cuerpo as Record<string, unknown>).error ??
          cuerpo)
        : `Error HTTP ${respuesta.status}`
    throw new ApiError(respuesta.status, detalle)
  }
  return cuerpo as T
}

export function crearSolicitud(payload: CrearSolicitudPayload) {
  return request<CrearSolicitudResponse>('/api/solicitudes', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function evaluarSolicitud(
  idSolicitud: string,
  payload: EvaluarSolicitudPayload,
) {
  return request<ResultadoMotorApi>(`/api/solicitudes/${idSolicitud}/evaluar`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function obtenerOfertas(idSolicitud: string) {
  return request<OfertaApi[]>(`/api/solicitudes/${idSolicitud}/ofertas`)
}

export function seleccionarOferta(
  idSolicitud: string,
  idOferta: number,
  monto?: number,
  plazo?: number,
) {
  return request<OfertaApi>(
    `/api/solicitudes/${idSolicitud}/ofertas/seleccionar`,
    {
      method: 'POST',
      body: JSON.stringify({
        id_oferta: idOferta,
        ...(monto != null ? { monto } : {}),
        ...(plazo != null ? { plazo } : {}),
      }),
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
  decision: string | null
  nombre_cliente: string
  num_cedula: string
  tipo_documento: string | null
  ocupacion: string | null
  linea_credito: string | null
  destino_credito: string | null
  plazo_deseado_meses: number | null
  evaluacion: EvaluacionResumenApi | null
}

export interface CausalSolicitudApi {
  codigo: string
  descripcion: string
  activa: boolean
}

export interface SolicitudDetalleApi extends SolicitudResumenApi {
  datos_laborales: {
    tipo_contrato: string | null
    meses_continuidad: number | null
    ingreso_mensual: string | null
    otros_ingresos: string | null
    anios_camara_comercio: string | null
  } | null
  contacto_vivienda: {
    estrato: number | null
    personas_a_cargo: number | null
    tipo_vivienda: string | null
  } | null
  causales: CausalSolicitudApi[]
  ofertas: OfertaApi[]
  desembolso: DesembolsoApi | null
}

export interface FiltrosSolicitudes {
  estado?: string
  decision?: string
  busqueda?: string
  limite?: number
  offset?: number
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

// ---------- Desembolso ----------

export interface BancoApi {
  id_banco: number
  codigo_ach: string | null
  nombre: string
}

export function listarBancos() {
  return request<BancoApi[]>('/api/bancos')
}

export interface RegistrarDesembolsoPayload {
  codigo_ach_banco: string
  numero_cuenta_cliente: string
  titular_cuenta?: string
  referencia_pago?: string
  vehiculo?: {
    producto_a_financiar: string
    marca?: string
    referencia?: string
    modelo?: string
    color?: string
    valor_moto_iva?: number
  }
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

export function registrarDesembolso(
  idSolicitud: string,
  payload: RegistrarDesembolsoPayload,
) {
  return request<DesembolsoApi>(`/api/solicitudes/${idSolicitud}/desembolso`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
