/**
 * Traducción entre las etiquetas del frontend y los enums del backend
 * (TipoIdentificacion, Ocupacion, TipoContrato de models/enums.py).
 */

import type { DatosSolicitud } from '../ui/CrearSolicitud'
import type {
  CrearSolicitudPayload,
  EvaluarSolicitudPayload,
} from '../api/originacionApi'
import {
  calcularCupoSugerido,
  TASA_MENSUAL_REFERENCIA,
} from './resultado-evaluacion'

/** Datos de identidad capturados en los pasos 1-6 del flujo. */
export interface IdentidadSolicitante {
  tipoDocumento: string
  numeroDocumento: string
  nombres: string
  apellidos: string
  fechaNacimiento: string
  nacionalidad: string
}

/** Backend TipoIdentificacion: CC=1, NIT=2, PJE=3, CE=4, PAS=5, PPT=6, TI=7, DNI=8, PEP=9. */
const TIPO_DOCUMENTO_API: Record<string, string> = {
  CC: '1',
  NIT: '2',
  CE: '4',
  PAS: '5',
  PPT: '6',
  TI: '7',
  DNI: '8',
  PEP: '9',
}

export function tipoDocumentoApi(codigo: string): string {
  return TIPO_DOCUMENTO_API[codigo.trim().toUpperCase()] ?? codigo
}

/** Ocupación del select → (ocupacion, tipo_contrato) del backend. */
export function ocupacionApi(label: string): {
  ocupacion: string
  tipoContrato: string | null
} {
  switch (label) {
    case 'Empleado Término Indefinido':
      return { ocupacion: 'Empleado', tipoContrato: 'Indefinido' }
    case 'Empleado Término Fijo':
      return { ocupacion: 'Empleado', tipoContrato: 'Fijo' }
    case 'Prestador de Servicios':
      return { ocupacion: 'Empleado', tipoContrato: 'Obra o Labor' }
    case 'Pensionado':
      return { ocupacion: 'Pensionado', tipoContrato: 'NA' }
    case 'Independiente':
    default:
      return { ocupacion: 'Independiente', tipoContrato: null }
  }
}

export function primerApellido(apellidos: string): string {
  return apellidos.trim().split(/\s+/)[0] ?? ''
}

export function construirCrearSolicitudPayload(
  identidad: IdentidadSolicitante,
  solicitud: DatosSolicitud,
  sesionCaptura?: string,
): CrearSolicitudPayload {
  const { ocupacion, tipoContrato } = ocupacionApi(solicitud.ocupacion)
  return {
    cliente: {
      tipo_documento: tipoDocumentoApi(identidad.tipoDocumento),
      num_cedula: identidad.numeroDocumento,
      nombre_completo:
        `${identidad.nombres} ${identidad.apellidos}`.trim() || 'Sin nombre',
      primer_apellido: primerApellido(identidad.apellidos),
      fecha_nacimiento: identidad.fechaNacimiento,
      ocupacion,
      nacionalidad: identidad.nacionalidad || 'Colombia',
    },
    datos_laborales: {
      tipo_contrato: tipoContrato,
      meses_continuidad: solicitud.mesesContinuidad ?? null,
      ingreso_mensual: solicitud.ingresosMensuales,
      otros_ingresos: 0,
      anios_camara_comercio: solicitud.aniosCamara ?? null,
    },
    contacto_vivienda: {},
    linea_credito: solicitud.lineaCredito,
    destino_credito: solicitud.destinoCredito,
    plazo_deseado_meses: solicitud.plazoMeses,
    ...(sesionCaptura ? { sesion_captura: sesionCaptura } : {}),
  }
}

export interface OrigenConsulta {
  origen: 'demo' | 'experian'
  escenarioMock: string
}

/**
 * La solicitud de evaluación usa el cupo referencial como saldo a
 * financiar: es el insumo de la política de capacidad; el motor
 * devuelve el cupo_sugerido real.
 */
export function construirEvaluacionPayload(
  solicitud: DatosSolicitud,
  origen: OrigenConsulta,
  extras?: { primerApellido?: string; tieneMultasRunt?: boolean },
): EvaluarSolicitudPayload {
  const { monto } = calcularCupoSugerido(
    solicitud.ingresosMensuales,
    solicitud.egresosMensuales,
    solicitud.plazoMeses || 36,
  )
  return {
    saldo_financiar: Math.max(monto, 1),
    plazo: solicitud.plazoMeses || 36,
    tasa: TASA_MENSUAL_REFERENCIA,
    primer_apellido: extras?.primerApellido,
    tiene_multas_runt: extras?.tieneMultasRunt ?? false,
    consultar_experian: origen.origen === 'experian',
    escenario_mock:
      origen.origen === 'demo' ? origen.escenarioMock || 'aprobado' : null,
  }
}
