/**
 * Adaptadores para las vistas del panel que consumen las solicitudes
 * reales del backend (GET /api/solicitudes). Traduce los enums del
 * esquema (estado/decisión) a la insignia visual del panel.
 */

import { useCallback, useEffect, useState } from 'react'
import {
  listarSolicitudes,
  type FiltrosSolicitudes,
  type SolicitudResumenApi,
} from '../../../features/credit-origination/api/originacionApi'
import type { EstadoSolicitud } from './underwritingEngine'

export type EstadoVisual = EstadoSolicitud

const ESTADOS_POSITIVOS = new Set(['aprobada', 'desembolsada'])
const ESTADOS_NEGATIVOS = new Set(['rechazada', 'cancelada'])

/**
 * La decisión del motor manda; si aún no hay evaluación se usa el
 * estado del ciclo de vida de la solicitud. `creada`/`en_evaluacion`
 * sin decisión son pendientes de evaluación (no "requieren revisión",
 * que es el perfil gris decidido por el motor).
 */
export function estadoVisual(s: SolicitudResumenApi): EstadoVisual {
  if (s.decision === 'aprobado' || ESTADOS_POSITIVOS.has(s.estado)) {
    return 'APROBADO'
  }
  if (s.decision === 'rechazado' || ESTADOS_NEGATIVOS.has(s.estado)) {
    return 'RECHAZADO'
  }
  if (
    s.decision == null &&
    (s.estado === 'creada' || s.estado === 'en_evaluacion')
  ) {
    return 'PENDIENTE'
  }
  return 'REQUIERE_REVISION'
}

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

interface EstadoCarga {
  datos: SolicitudResumenApi[]
  cargando: boolean
  error: string | null
}

export function useSolicitudes(filtros?: FiltrosSolicitudes) {
  const [estado, setEstado] = useState<EstadoCarga>({
    datos: [],
    cargando: true,
    error: null,
  })
  const clave = JSON.stringify(filtros ?? {})

  const recargar = useCallback(() => {
    setEstado((prev) => ({ ...prev, cargando: true, error: null }))
    listarSolicitudes(filtros)
      .then((datos) => setEstado({ datos, cargando: false, error: null }))
      .catch((err: unknown) =>
        setEstado({
          datos: [],
          cargando: false,
          error:
            err instanceof Error
              ? err.message
              : 'Error consultando solicitudes',
        }),
      )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clave])

  useEffect(() => {
    recargar()
  }, [recargar])

  return { ...estado, recargar }
}
