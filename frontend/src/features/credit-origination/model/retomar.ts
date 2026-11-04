/**
 * Paso de aterrizaje al retomar ("Continuar") una solicitud persistida.
 * Se deriva de lo que realmente quedó guardado —no de que la solicitud
 * exista— para no saltar a la evaluación con pasos pendientes.
 */

import type { EvidenciaApi, SolicitudDetalleApi } from '../api/originacionApi'
import type { PasoOriginacion } from './etapas-originacion'

/** Las dos caras de la cédula: el OCR del paso 2 las requiere. */
const EVIDENCIA_CEDULA = new Set(['cedula_frontal', 'cedula_reverso'])

export function pasoParaRetomar(
  datos: SolicitudDetalleApi,
  evidencias: EvidenciaApi[],
): PasoOriginacion {
  // Paso 1: Habeas Data + canal de contacto (el OTP sale por teléfono o
  // correo; sin ninguno la formalización no puede firmar).
  const contacto = datos.contacto_vivienda
  const sinContacto = !contacto?.telefono?.trim() && !contacto?.correo?.trim()
  if (!datos.consentimientos?.length || sinContacto) {
    return 1
  }
  // Paso 2: evidencia documental de la cédula (los doc_* de legalización
  // son producto posterior, no prueban la captura). El paso 3 (datos y
  // políticas) quedó persistido al radicar, así que no se re-aterriza ahí.
  const caras = new Set(
    evidencias.map((e) => e.tipo).filter((t) => EVIDENCIA_CEDULA.has(t)),
  )
  if (caras.size < EVIDENCIA_CEDULA.size) {
    return 2
  }
  // Paso 4: perfil económico (ingreso mensual alimenta la capacidad del
  // motor; sin él la evaluación no tiene insumo).
  if (datos.datos_laborales?.ingreso_mensual == null) {
    return 4
  }
  return 5
}
