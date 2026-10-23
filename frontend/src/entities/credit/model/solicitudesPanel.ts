/**
 * Adaptadores para las vistas del panel que consumen las solicitudes
 * reales del backend (GET /api/solicitudes). Traduce los enums del
 * esquema (estado/decisión) a la insignia visual del panel.
 */

import { useQuery } from '@tanstack/react-query'
import {
  listarSolicitudes,
  type FiltrosSolicitudes,
  type SolicitudResumenApi,
} from '../../../features/credit-origination/api/originacionApi'

/**
 * Estados visuales de una solicitud en el panel. La decisión del motor
 * es binaria; `REQUIERE_REVISION` queda solo para evaluaciones/estados
 * legados (ya no se emite).
 */
export type EstadoSolicitud =
  'APROBADO' | 'RECHAZADO' | 'REQUIERE_REVISION' | 'PENDIENTE'

export type EstadoVisual = EstadoSolicitud

const ESTADOS_POSITIVOS = new Set(['aprobada', 'desembolsada'])
const ESTADOS_NEGATIVOS = new Set(['rechazada', 'cancelada'])

/**
 * La decisión del motor manda; si aún no hay evaluación se usa el
 * estado del ciclo de vida de la solicitud. `creada`/`en_evaluacion`
 * sin decisión son pendientes de evaluación.
 */
export function estadoVisual(s: SolicitudResumenApi): EstadoVisual {
  if (s.decision === 'aprobado' || ESTADOS_POSITIVOS.has(s.estado)) {
    return 'APROBADO'
  }
  if (
    s.decision === 'rechazado' ||
    ESTADOS_NEGATIVOS.has(s.estado) ||
    // Legado: 'en_revision' era la espera del comité; sin comité se
    // muestra como no aprobada.
    s.estado === 'en_revision'
  ) {
    return 'RECHAZADO'
  }
  if (
    s.decision == null &&
    (s.estado === 'creada' || s.estado === 'en_evaluacion')
  ) {
    return 'PENDIENTE'
  }
  return 'RECHAZADO'
}

/**
 * Vista del estado para la UI. La decisión visible es binaria para
 * todos los roles; los detalles sensibles (score, causales) se ocultan
 * al asesor en el detalle, no en el estado.
 */
export function estadoParaVista(s: SolicitudResumenApi): EstadoVisual {
  return estadoVisual(s)
}

// Solicitudes retomables desde la lista o el detalle: aún no están
// firmadas ni cerradas (rechazada, desembolsada o cancelada son
// estados finales del flujo de originación).
export const ESTADOS_RETOMABLES = new Set([
  'creada',
  'en_evaluacion',
  'aprobada',
])

export const OCUPACION_LABELS: Record<string, string> = {
  empleado: 'Empleado',
  independiente: 'Independiente',
  pensionado: 'Pensionado',
  fuerzas_militares: 'Fuerzas militares',
}

export const ESTADO_LABELS: Record<string, string> = {
  creada: 'Creada',
  en_evaluacion: 'En evaluación',
  aprobada: 'Aprobada',
  rechazada: 'Rechazada',
  en_revision: 'En revisión',
  desembolsada: 'Desembolsada',
  cancelada: 'Cancelada',
}

export function etiquetaSolicitud(s: SolicitudResumenApi): string {
  return s.num_solicitud != null
    ? `#${s.num_solicitud}`
    : s.id_solicitud.slice(0, 8)
}

export function numero(valor: string | null | undefined): number | null {
  if (valor == null || valor.trim() === '') return null
  const n = Number(valor)
  return Number.isFinite(n) ? n : null
}

/**
 * Solicitudes del backend con caché compartida (TanStack Query):
 * navegar entre /solicitudes, /resumen y el panel reutiliza la misma
 * consulta sin golpear la API cada vez, y las mutaciones del detalle
 * la invalidan para que la lista vuelva fresca.
 */
export function useSolicitudes(
  filtros?: FiltrosSolicitudes,
  opciones?: { refetchIntervalMs?: number },
) {
  const consulta = useQuery({
    queryKey: ['solicitudes', filtros ?? null],
    queryFn: () => listarSolicitudes(filtros),
    refetchInterval: opciones?.refetchIntervalMs,
  })
  return {
    datos: consulta.data ?? ([] as SolicitudResumenApi[]),
    cargando: consulta.isPending,
    error:
      consulta.error instanceof Error
        ? consulta.error.message
        : consulta.error
          ? 'Error consultando solicitudes'
          : null,
    recargar: consulta.refetch,
    /** Timestamp de la última respuesta exitosa (indicador de frescura). */
    actualizadoEn: consulta.dataUpdatedAt || null,
    /** true durante cualquier fetch — inicial o refresco en segundo plano. */
    sincronizando: consulta.isFetching,
  }
}
