/**
 * Borrador local de la originación: si el navegador se cierra o se
 * interrumpe el flujo, el asesor puede retomar donde quedó. Los datos
 * sensibles se guardan en localStorage del equipo del asesor (mismo
 * alcance que la sesión); cuando la solicitud se formaliza o se
 * descarta, el borrador se elimina.
 */

import type { DatosValidacion } from '../ui/ValidacionInicial'
import type { DatosAutorizacion } from '../ui/AutorizacionDatos'
import type { ResultadoBiometrico } from '../ui/CapturaCedula'
import type { ResultadoOCR } from '../ui/ProcesamientoOCR'
import type { DatosRevisados } from '../ui/RevisionDatos'
import type { ResultadoFinal } from '../ui/ResultadoValidacion'
import type { DatosSolicitud } from '../ui/CrearSolicitud'
import type { DatosConsulta } from '../ui/PreparacionConsulta'
import type { ResultadoConsultaEnCurso } from '../ui/ConsultaEnCurso'
import type { OfertaSeleccionada } from '../ui/ResultadoCredito'
import type { ResultadoEvaluacionCredito } from './resultado-evaluacion'

export interface ContextoOriginacion {
  validacion?: DatosValidacion
  autorizacion?: DatosAutorizacion
  biometria?: ResultadoBiometrico
  ocr?: ResultadoOCR
  revision?: DatosRevisados
  resultado?: ResultadoFinal
  solicitud?: DatosSolicitud
  /** ID persistido en POST /api/solicitudes (paso 7). */
  idSolicitud?: string
  consulta?: DatosConsulta
  resultadoConsulta?: ResultadoConsultaEnCurso
  resultadoEvaluacion?: ResultadoEvaluacionCredito
  ofertaSeleccionada?: OfertaSeleccionada
}

export interface BorradorOriginacion {
  version: 1
  paso: number
  contexto: ContextoOriginacion
  formalizacionIniciada: boolean
  guardadoEn: string
}

const CLAVE = 'inversiones-pacifico:borrador-originacion'

export function cargarBorrador(): BorradorOriginacion | null {
  try {
    const crudo = localStorage.getItem(CLAVE)
    if (!crudo) return null
    const borrador = JSON.parse(crudo) as BorradorOriginacion
    if (borrador.version !== 1 || !borrador.contexto || !borrador.paso) {
      return null
    }
    return borrador
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
