import { useState } from 'react'
import CapturaCedula, { type ResultadoBiometrico } from './CapturaCedula'
import RevisionDatos, { type DatosRevisados } from './RevisionDatos'
import type { ResultadoOCR } from '../model/resultado-ocr'
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
  onContinue: (resultado: ResultadoEvidenciaYDatos) => void
  onBack?: () => void
}

// El OCR corre por debajo: la extracción llega lista a la revisión del
// asesor sin pantalla de carga intermedia.
function EvidenciaYDatos({
  numeroDocumento,
  onContinue,
  onBack,
}: EvidenciaYDatosProps) {
  const [biometria, setBiometria] = useState<ResultadoBiometrico | null>(null)
  const [ocr] = useState<ResultadoOCR>({
    numeroDocumento: numeroDocumento ?? '',
    nombres: '',
    apellidos: '',
    fechaExpedicion: '',
    vigente: true,
    calidadImagen: 'aprobada',
    alteraciones: false,
  })

  return (
    <div className="evidencia-datos">
      <CabeceraEtapaOriginacion
        paso={3}
        titulo="Evidencia y datos personales"
        descripcion="Captura la cédula y la prueba de vida del cliente; el sistema extrae los datos por debajo y tú confirmas que concuerdan."
      />
      <SeguimientoOriginacion pasoActual={3} />
      {!biometria ? (
        <CapturaCedula
          compacto
          onContinue={(resultado) => setBiometria(resultado)}
          onBack={onBack}
        />
      ) : (
        <RevisionDatos
          compacto
          inicial={
            numeroDocumento
              ? { numeroIdentificacion: numeroDocumento }
              : undefined
          }
          onContinue={(datos) =>
            onContinue({ biometria, ocr, revision: datos })
          }
          onBack={() => setBiometria(null)}
        />
      )}
    </div>
  )
}

export default EvidenciaYDatos
