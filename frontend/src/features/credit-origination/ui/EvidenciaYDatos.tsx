import { Smartphone, Zap } from 'lucide-react'
import CapturaCedula, { type ResultadoBiometrico } from './CapturaCedula'
import RevisionDatos, { type DatosRevisados } from './RevisionDatos'
import type { ResultadoOCR } from '../model/resultado-ocr'
import type { DatosValidacion } from '../model/politicas-clave'
import type { DatosEsperadosOCR, ResultadoOCRApi } from '../api/originacionApi'
import CabeceraEtapaOriginacion from './CabeceraEtapaOriginacion'
import SeguimientoOriginacion from './SeguimientoOriginacion/SeguimientoOriginacion'
import './CabeceraEtapaOriginacion.css'
import './EvidenciaYDatos.css'

export interface ResultadoDatosYPoliticas {
  ocr?: ResultadoOCR
  revision: DatosRevisados
  validacion: DatosValidacion
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
    // El PPT se lee pero es un documento rechazado: solo se aceptan colombianos.
    calidadImagen:
      api.disponible && Boolean(api.tipo_cedula) && api.tipo_cedula !== 'ppt'
        ? 'aprobada'
        : 'rechazada',
    alteraciones,
    tipoCedula: api.tipo_cedula || null,
  }
}

interface CapturaEvidenciaProps {
  /** Datos ya conocidos (solo al retomar) contra los que el OCR compara. */
  datosEsperados?: DatosEsperadosOCR
  onContinue: (biometria: ResultadoBiometrico) => void
  onBack?: () => void
}

/** Paso 2: el cliente sube cédula y video desde el celular (QR). */
export function CapturaEvidencia({
  datosEsperados,
  onContinue,
  onBack,
}: CapturaEvidenciaProps) {
  return (
    <div className="evidencia-datos">
      <CabeceraEtapaOriginacion paso={2} titulo="Evidencia del cliente">
        <p className="evidencia-datos__tagline">
          <Zap size={14} aria-hidden="true" />
          Rápido y fácil
          <span className="evidencia-datos__tagline-sep" aria-hidden="true" />
          <Smartphone size={14} aria-hidden="true" />
          sin instalar apps
        </p>
      </CabeceraEtapaOriginacion>
      <SeguimientoOriginacion pasoActual={2} />
      <CapturaCedula
        compacto
        datosEsperados={datosEsperados}
        onContinue={onContinue}
        onBack={onBack}
      />
    </div>
  )
}

interface DatosYPoliticasProps {
  biometria: ResultadoBiometrico
  revisionPrevia?: DatosRevisados
  validacionPrevia?: DatosValidacion
  /** Consentimiento Habeas Data del paso 1: con él «Consultar» pega al
   * backend; sin él queda la verificación manual en el portal SIMIT. */
  autorizoHabeas?: boolean
  onContinue: (resultado: ResultadoDatosYPoliticas) => void
  onBack?: () => void
}

/**
 * Paso 3: datos extraídos de la cédula (OCR) + verificación de políticas
 * clave. El OCR corre por debajo: la extracción llega lista sin pantalla
 * de carga intermedia.
 */
export function DatosYPoliticas({
  biometria,
  revisionPrevia,
  validacionPrevia,
  autorizoHabeas = false,
  onContinue,
  onBack,
}: DatosYPoliticasProps) {
  return (
    <div className="evidencia-datos">
      <CabeceraEtapaOriginacion
        paso={3}
        titulo="Datos personales y políticas"
      />
      <SeguimientoOriginacion pasoActual={3} />
      <RevisionDatos
        compacto
        // Lo ya confirmado (volver desde el paso 4 o retomar) prima sobre
        // lo leído por el OCR.
        inicial={revisionPrevia}
        inicialPoliticas={validacionPrevia}
        autorizoHabeas={autorizoHabeas}
        ocr={biometria.ocr ?? null}
        onContinue={(revision, validacion) =>
          onContinue({
            ocr: resumirOCR(biometria.ocr, validacion.numeroDocumento),
            revision,
            validacion,
          })
        }
        onBack={onBack}
      />
    </div>
  )
}
