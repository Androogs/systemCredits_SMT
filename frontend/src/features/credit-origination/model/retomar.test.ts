/**
 * "Continuar" una solicitud persistida: el paso de aterrizaje se deriva
 * de lo que realmente quedó guardado (consentimiento, evidencias de
 * cédula, perfil económico), no de que la solicitud exista.
 */

import { describe, expect, it } from 'vitest'
import type { EvidenciaApi, SolicitudDetalleApi } from '../api/originacionApi'
import { pasoParaRetomar } from './retomar'

function detalle(
  parcial: Partial<SolicitudDetalleApi> = {},
): SolicitudDetalleApi {
  return {
    id_solicitud: 's1',
    num_solicitud: 1,
    fecha_hora: '2026-01-01T00:00:00Z',
    estado: 'creada',
    descripcion_estado: null,
    decision: null,
    nombre_cliente: 'Cliente Ficticio',
    num_cedula: '1000000001',
    tipo_documento: '1',
    ocupacion: 'empleado',
    linea_credito: 'Crédito Directo',
    destino_credito: 'Financiamiento de Vehículos',
    plazo_deseado_meses: 24,
    fecha_hora_firma: null,
    evaluacion: null,
    datos_laborales: {
      tipo_contrato: 'indefinido',
      meses_continuidad: 12,
      ingreso_mensual: '5000000',
      otros_ingresos: '0',
      anios_camara_comercio: null,
    },
    contacto_vivienda: {
      estrato: null,
      personas_a_cargo: null,
      tipo_vivienda: null,
      telefono: '3001234567',
      correo: 'c@correo.com',
    },
    causales: [],
    ofertas: [],
    desembolso: null,
    consentimientos: [
      {
        version_texto: 'v1',
        hash_texto: 'abc',
        canal: 'web_asesor',
        ip: null,
        fecha_aceptacion: '2026-01-01T00:00:00Z',
      },
    ],
    ...parcial,
  }
}

function evidencia(tipo: string): EvidenciaApi {
  return {
    id_evidencia: 1,
    tipo,
    nombre_original: null,
    mime: 'image/jpeg',
    tamano_bytes: 10,
    hash_sha256: 'x',
    creado_en: '2026-01-01T00:00:00Z',
  }
}

const CEDULA_COMPLETA = [
  evidencia('cedula_frontal'),
  evidencia('cedula_reverso'),
]

describe('pasoParaRetomar', () => {
  it('sin consentimiento Habeas aterriza en la autorización (paso 1)', () => {
    expect(
      pasoParaRetomar(detalle({ consentimientos: [] }), CEDULA_COMPLETA),
    ).toBe(1)
    expect(
      pasoParaRetomar(detalle({ consentimientos: undefined }), CEDULA_COMPLETA),
    ).toBe(1)
  })

  it('consentimiento sin canal de contacto vuelve al paso 1 (el OTP lo necesita)', () => {
    const sinContacto = detalle()
    sinContacto.contacto_vivienda = {
      estrato: null,
      personas_a_cargo: null,
      tipo_vivienda: null,
    }
    expect(pasoParaRetomar(sinContacto, CEDULA_COMPLETA)).toBe(1)
  })

  it('autorización lista pero sin evidencias de cédula aterriza en captura (paso 2)', () => {
    expect(pasoParaRetomar(detalle(), [])).toBe(2)
    expect(pasoParaRetomar(detalle(), [evidencia('cedula_frontal')])).toBe(2)
  })

  it('los documentos de legalización no cuentan como evidencia de cédula', () => {
    expect(pasoParaRetomar(detalle(), [evidencia('doc_pagare')])).toBe(2)
  })

  it('evidencia lista pero sin perfil económico aterriza en Crear solicitud (paso 4)', () => {
    expect(
      pasoParaRetomar(detalle({ datos_laborales: null }), CEDULA_COMPLETA),
    ).toBe(4)
  })

  it('perfil sin ingreso mensual también aterriza en el paso 4', () => {
    const sinIngreso = detalle()
    sinIngreso.datos_laborales = {
      ...sinIngreso.datos_laborales!,
      ingreso_mensual: null,
    }
    expect(pasoParaRetomar(sinIngreso, CEDULA_COMPLETA)).toBe(4)
  })

  it('todo persistido aterriza en evaluación y resultado (paso 5)', () => {
    expect(pasoParaRetomar(detalle(), CEDULA_COMPLETA)).toBe(5)
  })
})
