/**
 * Puerta SIMIT del paso 3: con documento + consentimiento Habeas Data
 * la consulta sale sola al montar el paso (el asesor no marca nada) y
 * se repite sola si cambia la persona consultada. La lógica de
 * decisión queda en este módulo puro para probarla sin DOM.
 */

import { tipoDocumentoApi } from './mapeos-api'
import { numeroDocumentoSchema } from '../schemas/persona'
import type { SimitConsultaResultado } from '../api/originacionApi'

/**
 * Llave de la consulta: la persona = tipo (enum del API) + número.
 * Cambiar documento, tipo de documento o nacionalidad produce otra
 * llave (o ninguna mientras falte un dato), lo que invalida la
 * consulta anterior y la re-dispara.
 */
export function claveSimit(
  tipoDocumento: string,
  numeroDocumento: string,
): string {
  const numero = numeroDocumento.replace(/\D/g, '')
  if (!tipoDocumento.trim() || !numero) return ''
  return `${tipoDocumentoApi(tipoDocumento)}:${numero}`
}

/**
 * El disparo automático exige el documento completo (la misma regla
 * del formulario: 6-10 dígitos). Sin este gate cada tecla mientras el
 * asesor digita produce otra llave y saldría una consulta por dígito.
 */
export function documentoCompletoSimit(numeroDocumento: string): boolean {
  return numeroDocumentoSchema.safeParse(numeroDocumento.replace(/\D/g, ''))
    .success
}

export type EstadoSimit =
  | { tipo: 'con_deuda'; tieneMultas: true; mensaje: string }
  | { tipo: 'paz_y_salvo'; tieneMultas: false; mensaje: string }
  | { tipo: 'manual'; tieneMultas: null; mensaje: null }

/**
 * Interpreta la respuesta del endpoint: deuda/paz y salvo cuando el
 * proveedor respondió, o fallback a la verificación manual (popup del
 * portal) cuando está deshabilitado o no respondió.
 */
export function interpretarSimit(res: SimitConsultaResultado): EstadoSimit {
  if (!res.habilitado || res.tiene_multas == null) {
    return { tipo: 'manual', tieneMultas: null, mensaje: null }
  }
  if (res.tiene_multas) {
    const monto =
      res.total_deuda != null
        ? ` por $${Number(res.total_deuda).toLocaleString('es-CO')}`
        : ''
    const items = res.total_items ? ` en ${res.total_items} registro(s)` : ''
    return {
      tipo: 'con_deuda',
      tieneMultas: true,
      mensaje: `SIMIT reporta deuda pendiente${monto}${items}.`,
    }
  }
  return {
    tipo: 'paz_y_salvo',
    tieneMultas: false,
    mensaje: 'SIMIT: paz y salvo, sin deuda pendiente.',
  }
}
