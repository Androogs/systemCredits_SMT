import { useState } from 'react'
import CapturaCedula, { type ResultadoBiometrico } from './CapturaCedula'
import RevisionDatos, { type DatosRevisados } from './RevisionDatos'
import type { ResultadoOCR } from '../model/resultado-ocr'
import type { DatosEsperadosOCR, ResultadoOCRApi } from '../api/originacionApi'
import CabeceraEtapaOriginacion from './CabeceraEtapaOriginacion'
import SeguimientoOriginacion from './SeguimientoOriginacion/SeguimientoOriginacion'
import './CabeceraEtapaOriginacion.css'
import './EvidenciaYDatos.css'

export interface ResultadoEvidenciaYDatos {
  biometria: ResultadoBiometrico
  ocr?: ResultadoOCR
  revision?: DatosRevisados
}

interface EvidenciaYDatosProps {
  numeroDocumento?: string
  /** Nombres/apellidos capturados en el paso 1, para comparar contra el OCR. */
  nombres?: string
  apellidos?: string
  /** Fecha de nacimiento (ISO) capturada en el paso 1. */
  fechaNacimiento?: string
  onContinue: (resultado: ResultadoEvidenciaYDatos) => void
  onBack?: () => void
}

/**
 * Resume el OCR del backend para el contexto de la originación.
 * Antes se enviaba un objeto quemado con campos vacíos: el paso siguiente
 * nunca recibía lo que se leyó de la cédula.
 */
function resumirOCR(
  api: ResultadoOCRApi | null | undefined,
  numeroDocumento?: string,
): ResultadoOCR | undefined {
  if (!api) return undefined
  const expira = api.fecha_expiracion?.valor ?? ''
  const hoy = new Date().toISOString().slice(0, 10)
  const alteraciones = api.advertencias.some(
    (a) =>
      (a.includes('anverso') && a.includes('reverso')) ||
      a.includes('cédulas distintas'),
  )
  return {
    numeroDocumento: api.numero_documento?.valor || numeroDocumento || '',
    nombres: api.nombres?.valor ?? '',
    apellidos: api.apellidos?.valor ?? '',
    fechaExpedicion: api.fecha_expedicion?.valor ?? '',
    fechaNacimiento: api.fecha_nacimiento?.valor ?? '',
    fechaExpiracion: expira,
    vigente: !expira || expira >= hoy,
    calidadImagen:
      api.disponible && Boolean(api.tipo_cedula) ? 'aprobada' : 'rechazada',
    alteraciones,
    tipoCedula: api.tipo_cedula || null,
  }
}

// El OCR corre por debajo: la extracción llega lista a la revisión del
// asesor sin pantalla de carga intermedia.
function EvidenciaYDatos({
  numeroDocumento,
  nombres,
  apellidos,
  fechaNacimiento,
  onContinue,
  onBack,
}: EvidenciaYDatosProps) {
  const [biometria, setBiometria] = useState<ResultadoBiometrico | null>(null)

  // Datos del paso 1 contra los que el OCR de la cédula compara.
  const datosEsperados: DatosEsperadosOCR = {
    ...(nombres ? { nombres } : {}),
    ...(apellidos ? { apellidos } : {}),
    ...(numeroDocumento ? { numero_documento: numeroDocumento } : {}),
    ...(fechaNacimiento ? { fecha_nacimiento: fechaNacimiento } : {}),
  }

  return (
    <div className="evidencia-datos">
      <CabeceraEtapaOriginacion paso={3} titulo="Documento y prueba de vida" />
      <SeguimientoOriginacion pasoActual={3} />
      {!biometria ? (
        <CapturaCedula
          compacto
          datosEsperados={datosEsperados}
          onContinue={(resultado) => setBiometria(resultado)}
          onBack={onBack}
        />
      ) : (
        <RevisionDatos
          compacto
          inicial={{
            ...(numeroDocumento
              ? { numeroIdentificacion: numeroDocumento }
              : {}),
            // Si el OCR leyó la fecha, su valor es el que se muestra y la
            // diferencia sale como advertencia; si no, precarga lo digitado.
            ...(fechaNacimiento && !biometria.ocr?.fecha_nacimiento?.valor
              ? { fechaNacimiento }
              : {}),
          }}
          ocr={biometria.ocr ?? null}
          onContinue={(datos) =>
            onContinue({
              biometria,
              ocr: resumirOCR(biometria.ocr, numeroDocumento),
              revision: datos,
            })
          }
          onBack={() => setBiometria(null)}
        />
      )}
    </div>
  )
}

export default EvidenciaYDatos
