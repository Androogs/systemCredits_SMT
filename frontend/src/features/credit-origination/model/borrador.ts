/**
 * Borrador local de la originación: si el navegador se cierra o se
 * interrumpe el flujo, el asesor puede retomar donde quedó. Los datos
 * sensibles se guardan en localStorage del equipo del asesor (mismo
 * alcance que la sesión); cuando la solicitud se formaliza o se
 * descarta, el borrador se elimina.
 */

import { z } from 'zod'
import type { DatosValidacion } from '../ui/ValidacionInicial'
import type { DatosAutorizacion } from '../ui/AutorizacionDatos'
import type { ResultadoBiometrico } from '../ui/CapturaCedula'
import type { ResultadoOCR } from './resultado-ocr'
import type { DatosRevisados } from '../ui/RevisionDatos'
import type { DatosSolicitud } from '../ui/CrearSolicitud'
import type { OfertaSeleccionada } from '../ui/ResultadoCredito'
import type { ResultadoEvaluacionCredito } from './resultado-evaluacion'

/** Valores que llegan del simulador al iniciar una solicitud. */
export interface SimulacionPrevia {
  /** Valor de la moto simulado → precarga "Valor moto + IVA". */
  valorMoto: number
  plazoMeses: number
  /** Adicionales agrupados (matrícula, SOAT, impuestos): solo referencia. */
  adicionales: number
  montoFinanciar: number
  cuotaMensual: number
}

export interface ContextoOriginacion {
  validacion?: DatosValidacion
  autorizacion?: DatosAutorizacion
  biometria?: ResultadoBiometrico
  ocr?: ResultadoOCR
  revision?: DatosRevisados
  solicitud?: DatosSolicitud
  /** ID persistido en POST /api/solicitudes. */
  idSolicitud?: string
  resultadoEvaluacion?: ResultadoEvaluacionCredito
  ofertaSeleccionada?: OfertaSeleccionada
  /** Simulación con la que el asesor abrió la solicitud. */
  simulacion?: SimulacionPrevia
}

export interface BorradorOriginacion {
  version: 1
  paso: number
  contexto: ContextoOriginacion
  formalizacionIniciada: boolean
  guardadoEn: string
}

const CLAVE = 'inversiones-pacifico:borrador-originacion'

// Valida el sobre del borrador; el contexto interno queda passthrough:
// cada paso valida su propia forma al consumirla.
const borradorSchema = z.object({
  version: z.literal(1),
  paso: z.number().int().min(1).max(5),
  contexto: z.custom<ContextoOriginacion>(
    (valor) => typeof valor === 'object' && valor !== null,
  ),
  formalizacionIniciada: z.boolean(),
  guardadoEn: z.string(),
})

export function cargarBorrador(): BorradorOriginacion | null {
  try {
    const crudo = localStorage.getItem(CLAVE)
    if (!crudo) return null
    const parseado = borradorSchema.safeParse(JSON.parse(crudo))
    return parseado.success ? parseado.data : null
  } catch {
    return null
  }
}

export function guardarBorrador(
  paso: number,
  contexto: ContextoOriginacion,
  formalizacionIniciada: boolean,
): void {
  try {
    const borrador: BorradorOriginacion = {
      version: 1,
      paso,
      contexto,
      formalizacionIniciada,
      guardadoEn: new Date().toISOString(),
    }
    localStorage.setItem(CLAVE, JSON.stringify(borrador))
  } catch {
    // localStorage lleno o bloqueado: el borrador es conveniencia,
    // nunca debe romper el flujo.
  }
}

export function limpiarBorrador(): void {
  try {
    localStorage.removeItem(CLAVE)
  } catch {
    // Ignorar: mismo razonamiento que en guardarBorrador.
  }
}
