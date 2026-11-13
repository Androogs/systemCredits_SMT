/** Cliente del reporte de comisiones del asesor (D134): GET
 * /api/comisiones/mias — solo rol asesor, sobre sus desembolsos
 * confirmados. */

import { useQuery } from '@tanstack/react-query'
import { env } from '../../../env'
import { fetchAutenticado } from '../../../shared/lib/fetchAutenticado'

const API = env.VITE_API_URL.replace(/\/$/, '')

export interface ComisionFila {
  id_desembolso: number
  num_desembolso: string | null
  num_solicitud: number | null
  nombre_cliente: string
  /** Radicador de la solicitud; solo lo puebla la vista del admin. */
  nombre_asesor: string | null
  fecha_desembolso: string | null
  capital: string
  /** Capital sin los gastos administrativos de originación. */
  base: string
  comision: string
}

export interface ComisionMes {
  /** Clave "YYYY-MM" en hora de Colombia. */
  mes: string
  desembolsos: number
  capital: string
  comision: string
}

export interface ComisionesResponse {
  porcentaje: string
  filas: ComisionFila[]
  meses: ComisionMes[]
  total_desembolsos: number
  total_capital: string
  total_base: string
  total_comision: string
}

async function request<T>(ruta: string): Promise<T> {
  const respuesta = await fetchAutenticado(`${API}${ruta}`)
  const cuerpo: unknown = await respuesta.json().catch(() => null)
  if (!respuesta.ok) {
    const detalle =
      cuerpo && typeof cuerpo === 'object' && 'detail' in cuerpo
        ? cuerpo.detail
        : `Error HTTP ${respuesta.status}`
    throw new Error(
      typeof detalle === 'string' ? detalle : JSON.stringify(detalle),
    )
  }
  return cuerpo as T
}

export function useComisiones() {
  return useQuery({
    queryKey: ['comisiones-mias'],
    queryFn: () => request<ComisionesResponse>('/api/comisiones/mias'),
    staleTime: 60_000,
  })
}
