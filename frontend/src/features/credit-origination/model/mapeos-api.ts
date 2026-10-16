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
  /** Contacto del cliente: OTP por WhatsApp y notificaciones por correo. */
  telefono?: string
  correo?: string
  /** true cuando el asesor registró la autorización Habeas Data (paso 2). */
  autorizoHabeas?: boolean
  /** Datos de la cédula confirmados en la revisión (paso 3). */
  fechaExpedicion?: string
  ciudadExpedicion?: string
  lugarNacimiento?: string
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

/** Inverso: código numérico del backend ('1') → etiqueta UI ('CC'). */
const TIPO_DOCUMENTO_UI: Record<string, string> = Object.fromEntries(
  Object.entries(TIPO_DOCUMENTO_API).map(([etiqueta, codigo]) => [
    codigo,
    etiqueta,
  ]),
)

export function tipoDocumentoUi(codigo: string | null | undefined): string {
  return TIPO_DOCUMENTO_UI[codigo ?? ''] ?? codigo ?? 'CC'
}

/**
 * Ocupación del select (4 valores) + tipo de contrato elegido cuando
 * es Empleado → (ocupacion, tipo_contrato) del backend
 * (models/enums.py). Pensionado y Fuerzas Militares no tienen
 * contrato: el motor los evalúa con matriz propia → 'NA'.
 */
export function ocupacionApi(
  ocupacion: string,
  tipoContrato: string,
): {
  ocupacion: string
  tipoContrato: string | null
} {
  switch (ocupacion) {
    case 'Empleado':
      return { ocupacion: 'Empleado', tipoContrato: tipoContrato || null }
    case 'Pensionado':
      return { ocupacion: 'Pensionado', tipoContrato: 'NA' }
    case 'Fuerzas Militares':
      return { ocupacion: 'Fuerzas Militares', tipoContrato: 'NA' }
    case 'Independiente':
    default:
      return { ocupacion: 'Independiente', tipoContrato: null }
  }
}

export function primerApellido(apellidos: string): string {
  return apellidos.trim().split(/\s+/)[0] ?? ''
}

/** Acepta 'YYYY-MM-DD' o 'DD/MM/YYYY' y devuelve formato ISO. */
export function normalizarFecha(valor: string): string {
  const texto = valor.trim()
  if (/^\d{4}-\d{2}-\d{2}$/.test(texto)) return texto
  const ddmmyyyy = /^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$/.exec(texto)
  if (ddmmyyyy) {
    const [, dia, mes, anio] = ddmmyyyy
    return `${anio}-${mes.padStart(2, '0')}-${dia.padStart(2, '0')}`
  }
  return texto
}

export function construirCrearSolicitudPayload(
  identidad: IdentidadSolicitante,
  solicitud: DatosSolicitud,
  sesionCaptura?: string,
): CrearSolicitudPayload {
  const { ocupacion, tipoContrato } = ocupacionApi(
    solicitud.ocupacion,
    solicitud.tipoContrato,
  )
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
      fecha_expedicion: identidad.fechaExpedicion
        ? normalizarFecha(identidad.fechaExpedicion)
        : null,
      ciudad_expedicion: identidad.ciudadExpedicion || null,
      ciudad_nacimiento: identidad.lugarNacimiento || null,
    },
    datos_laborales: {
      tipo_contrato: tipoContrato,
      meses_continuidad: solicitud.mesesContinuidad ?? null,
      ingreso_mensual: solicitud.ingresosMensuales,
      otros_ingresos: 0,
      anios_camara_comercio: solicitud.aniosCamara ?? null,
      // Empleador (empleado/independiente) o entidad pagadora
      // (pensionado/FFMM): precarga el formulario de formalización.
      nombre_empresa:
        solicitud.empresa.trim() || solicitud.entidadPagadora.trim() || null,
    },
    contacto_vivienda: {
      telefono: identidad.telefono || null,
      correo: identidad.correo || null,
    },
    ...(identidad.autorizoHabeas ? { consentimiento: { aceptado: true } } : {}),
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
