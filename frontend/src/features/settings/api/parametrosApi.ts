import { env } from '../../../env'

const API = env.VITE_API_URL.replace(/\/$/, '')

export type ValorParametro = number | boolean | string | number[] | string[]
export type ParametrosMotor = Record<string, ValorParametro>

export interface RespuestaParametros {
  parametros: ParametrosMotor
  bloqueados_por_entorno: string[]
}

export class ErrorParametrosApi extends Error {
  readonly status: number

  constructor(status: number, detalle: unknown) {
    super(
      typeof detalle === 'string'
        ? detalle
        : JSON.stringify(detalle) || `Error HTTP ${status}`,
    )
    this.name = 'ErrorParametrosApi'
    this.status = status
  }
}

async function request(
  ruta: string,
  init?: RequestInit,
): Promise<RespuestaParametros> {
  const respuesta = await fetch(`${API}${ruta}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  const cuerpo: unknown = await respuesta.json().catch(() => null)

  if (!respuesta.ok) {
    const detalle =
      cuerpo && typeof cuerpo === 'object' && 'detail' in cuerpo
        ? cuerpo.detail
        : (cuerpo ?? `Error HTTP ${respuesta.status}`)
    throw new ErrorParametrosApi(respuesta.status, detalle)
  }

  if (
    !cuerpo ||
    typeof cuerpo !== 'object' ||
    !('parametros' in cuerpo) ||
    !cuerpo.parametros ||
    typeof cuerpo.parametros !== 'object' ||
    Array.isArray(cuerpo.parametros) ||
    !('bloqueados_por_entorno' in cuerpo) ||
    !Array.isArray(cuerpo.bloqueados_por_entorno) ||
    !cuerpo.bloqueados_por_entorno.every(
      (campo): campo is string => typeof campo === 'string',
    )
  ) {
    throw new Error('La API devolvió una respuesta de parámetros inválida.')
  }

  return cuerpo as RespuestaParametros
}

export function obtenerParametros() {
  return request('/api/parametros')
}

export function actualizarParametros(cambios: ParametrosMotor) {
  return request('/api/parametros', {
    method: 'PUT',
    body: JSON.stringify(cambios),
  })
}

export function restablecerParametros() {
  return request('/api/parametros/reset', { method: 'POST' })
}
