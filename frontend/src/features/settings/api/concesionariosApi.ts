import { useQuery } from '@tanstack/react-query'
import { env } from '../../../env'
import { fetchAutenticado } from '../../../shared/lib/fetchAutenticado'

const API = env.VITE_API_URL.replace(/\/$/, '')

export interface MarcaResumen {
  marca: string
  sedes: string[]
  asesores: number
  radicadas: number
  creditos: number
  monto_usado: number
}

async function request<T>(ruta: string, init?: RequestInit): Promise<T> {
  const respuesta = await fetchAutenticado(`${API}${ruta}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
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

/** Resumen real por marca: sedes, asesores, radicadas y monto
 * financiado, agregado en servidor (Ajustes → Concesionarios). */
export function useMarcasResumen() {
  return useQuery({
    queryKey: ['marcas-resumen'],
    queryFn: () => request<MarcaResumen[]>('/api/catalogos/marcas-resumen'),
    staleTime: 30_000,
  })
}

/** Alta de marca: persiste en el catálogo y devuelve el resumen
 * actualizado. */
export function crearMarca(nombre: string) {
  return request<MarcaResumen[]>('/api/catalogos/marcas', {
    method: 'POST',
    body: JSON.stringify({ nombre }),
  })
}
