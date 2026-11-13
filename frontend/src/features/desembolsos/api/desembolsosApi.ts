/**
 * Cliente HTTP de la bandeja de desembolsos (operaciones):
 * paginación server-side por conteo, desembolso masivo y el cargue
 * de garantías al SGM (RUNT Pro) con sus headers de conteo.
 */

import { fetchAutenticado } from '../../../shared/lib/fetchAutenticado'
import {
  ApiError,
  listarSolicitudes,
  type FiltrosSolicitudes,
} from '../../credit-origination/api/originacionApi'

// ---------- Listados (reusan el contrato de /api/solicitudes) ----------

export function listarBandeja(estado: string, limite: number, offset: number) {
  const filtros: FiltrosSolicitudes = { estado, limite, offset }
  return listarSolicitudes(filtros)
}

export interface ConteoApi {
  total: number
}

export async function contarSolicitudes(estado: string): Promise<ConteoApi> {
  const params = new URLSearchParams({ estado })
  const respuesta = await fetchAutenticado(
    `/api/solicitudes/conteo?${params.toString()}`,
    { headers: { 'Content-Type': 'application/json' } },
  )
  const cuerpo: unknown = await respuesta.json().catch(() => null)
  if (respuesta.ok) return cuerpo as ConteoApi
  const detalle =
    cuerpo && typeof cuerpo === 'object'
      ? ((cuerpo as Record<string, unknown>).detail ??
        `Error HTTP ${respuesta.status}`)
      : `Error HTTP ${respuesta.status}`
  throw new ApiError(respuesta.status, detalle)
}

// ---------- Desembolso masivo ----------

export interface ResultadoDesembolsoItem {
  id_solicitud: string
  ok: boolean
  error?: string | null
}

export interface DesembolsoMasivoApi {
  procesadas: number
  fallidas: number
  resultados: ResultadoDesembolsoItem[]
}

export async function desembolsoMasivo(
  idSolicitudes: string[],
): Promise<DesembolsoMasivoApi> {
  const respuesta = await fetchAutenticado(
    '/api/solicitudes/desembolso-masivo',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id_solicitudes: idSolicitudes }),
    },
  )
  const cuerpo: unknown = await respuesta.json().catch(() => null)
  if (respuesta.ok) return cuerpo as DesembolsoMasivoApi
  const detalle =
    cuerpo && typeof cuerpo === 'object'
      ? ((cuerpo as Record<string, unknown>).detail ??
        `Error HTTP ${respuesta.status}`)
      : `Error HTTP ${respuesta.status}`
  throw new ApiError(respuesta.status, detalle)
}

// ---------- Cargue de garantías al RNGM (RUNTPRO) ----------

export interface ResultadoExportRunt {
  /** Prendas incluidas en el archivo. */
  garantias: number
  /** Campos por revisar antes de radicar en RUNTPRO. */
  advertencias: number
  nombreArchivo: string
}

/** Descarga el archivo plano .txt RNGM de la guía RUNTPRO GM Fase II;
 *  propaga ApiError(404) cuando no hay garantías pendientes. */
export async function descargarGarantiasRunt(
  incluirExportadas: boolean,
): Promise<ResultadoExportRunt> {
  const respuesta = await fetchAutenticado(
    `/api/cargas/garantias-runtpro?incluir_exportadas=${incluirExportadas}`,
  )
  if (!respuesta.ok) {
    const cuerpo: unknown = await respuesta.json().catch(() => null)
    const detalle =
      cuerpo && typeof cuerpo === 'object'
        ? ((cuerpo as Record<string, unknown>).detail ??
          `Error HTTP ${respuesta.status}`)
        : `Error HTTP ${respuesta.status}`
    throw new ApiError(respuesta.status, detalle)
  }
  const blob = await respuesta.blob()
  const disposicion = respuesta.headers.get('Content-Disposition') ?? ''
  const nombreArchivo =
    /filename="?([^";]+)"?/.exec(disposicion)?.[1] ?? 'garantias_runt.txt'
  const obj = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = obj
  a.download = nombreArchivo
  a.click()
  setTimeout(() => URL.revokeObjectURL(obj), 10_000)
  return {
    garantias: Number(respuesta.headers.get('X-Garantias-Exportadas') ?? 0),
    advertencias: Number(respuesta.headers.get('X-Advertencias') ?? 0),
    nombreArchivo,
  }
}

export interface OpcionesCargueExcel {
  hoja?: string
  desde?: number
  nit?: string
  /** 'txt' descarga el plano RNGM; 'excel' la hoja de revisión. */
  formato?: 'txt' | 'excel'
}

/** Cargue masivo desde el registro Excel externo: sube el archivo y
 *  descarga el plano RNGM (o la hoja de revisión). Solo toma las
 *  filas con ESTADO DE PAGO = PENDIENTE desde la fila indicada. */
export async function cargarGarantiasRuntExcel(
  archivo: File,
  opciones: OpcionesCargueExcel = {},
): Promise<ResultadoExportRunt> {
  const form = new FormData()
  form.append('archivo', archivo)
  if (opciones.hoja) form.append('hoja', opciones.hoja)
  if (opciones.desde) form.append('desde', String(opciones.desde))
  if (opciones.nit) form.append('nit', opciones.nit)
  const params = new URLSearchParams({ formato: opciones.formato ?? 'txt' })
  const respuesta = await fetchAutenticado(
    `/api/cargas/garantias-runtpro/excel?${params.toString()}`,
    { method: 'POST', body: form },
  )
  if (!respuesta.ok) {
    const cuerpo: unknown = await respuesta.json().catch(() => null)
    const detalle =
      cuerpo && typeof cuerpo === 'object'
        ? ((cuerpo as Record<string, unknown>).detail ??
          `Error HTTP ${respuesta.status}`)
        : `Error HTTP ${respuesta.status}`
    throw new ApiError(respuesta.status, detalle)
  }
  const blob = await respuesta.blob()
  const disposicion = respuesta.headers.get('Content-Disposition') ?? ''
  const nombreArchivo =
    /filename="?([^";]+)"?/.exec(disposicion)?.[1] ?? 'garantias_runt.txt'
  const obj = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = obj
  a.download = nombreArchivo
  a.click()
  setTimeout(() => URL.revokeObjectURL(obj), 10_000)
  return {
    garantias: Number(respuesta.headers.get('X-Garantias-Exportadas') ?? 0),
    advertencias: Number(respuesta.headers.get('X-Advertencias') ?? 0),
    nombreArchivo,
  }
}

export interface AdvertenciasRngm {
  pendientes: number
  advertencias: {
    num_solicitud: number | null
    cliente: string
    cedula: string
    mensaje: string
  }[]
}

/** Vista previa del cargue RNGM: pendientes y campos por corregir,
 *  sin generar archivo ni marcar garantías. */
export async function advertenciasGarantiasRunt(
  incluirExportadas: boolean,
): Promise<AdvertenciasRngm> {
  const respuesta = await fetchAutenticado(
    `/api/cargas/garantias-runtpro/advertencias?incluir_exportadas=${incluirExportadas}`,
  )
  const cuerpo: unknown = await respuesta.json().catch(() => null)
  if (respuesta.ok) return cuerpo as AdvertenciasRngm
  const detalle =
    cuerpo && typeof cuerpo === 'object'
      ? ((cuerpo as Record<string, unknown>).detail ??
        `Error HTTP ${respuesta.status}`)
      : `Error HTTP ${respuesta.status}`
  throw new ApiError(respuesta.status, detalle)
}
