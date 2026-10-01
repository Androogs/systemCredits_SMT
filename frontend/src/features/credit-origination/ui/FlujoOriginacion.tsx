import { useState } from 'react'
import ValidacionInicial, { type DatosValidacion } from './ValidacionInicial'
import AutorizacionDatos, { type DatosAutorizacion } from './AutorizacionDatos'
import CapturaCedula, { type ResultadoBiometrico } from './CapturaCedula'
import ProcesamientoOCR, { type ResultadoOCR } from './ProcesamientoOCR'
import RevisionDatos, { type DatosRevisados } from './RevisionDatos'
import ResultadoValidacion, { type ResultadoFinal } from './ResultadoValidacion'
import CrearSolicitud, { type DatosSolicitud } from './CrearSolicitud'
import PreparacionConsulta, { type DatosConsulta } from './PreparacionConsulta'
import ConsultaEnCurso, {
  type ResultadoConsultaEnCurso,
} from './ConsultaEnCurso'
import InformeCrediticio from './InformeCrediticio'
import EvaluacionIntegral from './EvaluacionIntegral'
import ResultadoCredito from './ResultadoCredito'
import type { ResultadoEvaluacionCreditoDemo } from '../model/resultado-evaluacion-demo'
import type { PasoOriginacion } from '../model/etapas-originacion'
import './FlujoOriginacion.css'

interface ContextoOriginacion {
  validacion?: DatosValidacion
  autorizacion?: DatosAutorizacion
  biometria?: ResultadoBiometrico
  ocr?: ResultadoOCR
  revision?: DatosRevisados
  resultado?: ResultadoFinal
  solicitud?: DatosSolicitud
  consulta?: DatosConsulta
  resultadoConsulta?: ResultadoConsultaEnCurso
  resultadoEvaluacion?: ResultadoEvaluacionCreditoDemo
}

const pasosFuturos: Record<number, { titulo: string; detalle: string }> = {
  10: {
    titulo: 'Informe Crediticio',
    detalle: 'Análisis de score y comportamiento histórico.',
  },
  11: {
    titulo: 'Evaluación Integral',
    detalle: 'Motor de políticas y decisión automatizada.',
  },
  12: {
    titulo: 'Resultado Final',
    detalle: 'Firma y desembolso del crédito.',
  },
}

function FlujoOriginacion() {
  const [pasoActual, setPasoActual] = useState<PasoOriginacion>(1)
  const [contexto, setContexto] = useState<ContextoOriginacion>({})
  const [formalizacionIniciada, setFormalizacionIniciada] = useState(false)

  const reiniciar = () => {
    setPasoActual(1)
    setContexto({})
    setFormalizacionIniciada(false)
  }

  const modificarSolicitud = () => {
    setContexto((actual) => {
      const contextoPrevio = { ...actual }
      delete contextoPrevio.consulta
      delete contextoPrevio.resultadoConsulta
      delete contextoPrevio.resultadoEvaluacion
      return contextoPrevio
    })
    setFormalizacionIniciada(false)
    setPasoActual(7)
  }

  const renderPasoActual = () => {
    if (pasoActual === 1) {
      return (
        <ValidacionInicial
          onContinue={(validacion) => {
            setContexto((actual) => ({ ...actual, validacion }))
            setPasoActual(2)
          }}
        />
      )
    }

    if (pasoActual === 2) {
      return (
        <AutorizacionDatos
          onBack={() => setPasoActual(1)}
          onContinue={(autorizacion) => {
            setContexto((actual) => ({ ...actual, autorizacion }))
            setPasoActual(3)
          }}
        />
      )
    }

    if (pasoActual === 3) {
      return (
        <CapturaCedula
          onBack={() => setPasoActual(2)}
          onContinue={(biometria) => {
            setContexto((actual) => ({ ...actual, biometria }))
            setPasoActual(4)
          }}
        />
      )
    }

    if (pasoActual === 4) {
      return (
        <ProcesamientoOCR
          onBack={() => setPasoActual(3)}
          onContinue={(ocr) => {
            setContexto((actual) => ({ ...actual, ocr }))
            setPasoActual(5)
          }}
        />
      )
    }

    if (pasoActual === 5) {
      return (
        <RevisionDatos
          onBack={() => setPasoActual(4)}
          onContinue={(revision) => {
            setContexto((actual) => ({ ...actual, revision }))
            setPasoActual(6)
          }}
        />
      )
    }

    if (pasoActual === 6) {
      return (
        <ResultadoValidacion
          onBack={() => setPasoActual(5)}
          onContinue={(resultado) => {
            setContexto((actual) => ({ ...actual, resultado }))
            setPasoActual(7)
          }}
        />
      )
    }

    if (pasoActual === 7) {
      return (
        <CrearSolicitud
          onBack={() => setPasoActual(6)}
          inicial={contexto.solicitud}
          onContinue={(solicitud) => {
            setContexto((actual) => ({
              ...actual,
              solicitud,
              consulta: undefined,
              resultadoConsulta: undefined,
              resultadoEvaluacion: undefined,
            }))
            setPasoActual(8)
          }}
        />
      )
    }

    if (pasoActual === 8) {
      return (
        <PreparacionConsulta
          onBack={() => setPasoActual(7)}
          inicial={contexto.consulta}
          onContinue={(consulta) => {
            setContexto((actual) => ({ ...actual, consulta }))
            setPasoActual(9)
          }}
        />
      )
    }

    if (pasoActual === 9) {
      return (
        <ConsultaEnCurso
          solicitante={contexto.consulta?.nombreCompleto}
          onBack={() => setPasoActual(8)}
          onContinue={(resultadoConsulta) => {
            setContexto((actual) => ({ ...actual, resultadoConsulta }))
            setPasoActual(10)
          }}
        />
      )
    }

    if (pasoActual === 10) {
      return (
        <InformeCrediticio
          onModificarDatos={modificarSolicitud}
          onContinue={() => setPasoActual(11)}
        />
      )
    }

    if (pasoActual === 11) {
      return (
        <EvaluacionIntegral
          solicitud={contexto.solicitud}
          onBack={() => setPasoActual(10)}
          onRevisionManual={(resultadoEvaluacion) => {
            setContexto((actual) => ({ ...actual, resultadoEvaluacion }))
            setFormalizacionIniciada(false)
            setPasoActual(12)
          }}
          onContinue={(resultadoEvaluacion) => {
            setContexto((actual) => ({ ...actual, resultadoEvaluacion }))
            setFormalizacionIniciada(false)
            setPasoActual(12)
          }}
        />
      )
    }

    if (pasoActual === 12 && contexto.resultadoEvaluacion) {
      return (
        <ResultadoCredito
          resultado={contexto.resultadoEvaluacion}
          formalizacionIniciada={formalizacionIniciada}
          onModificar={() => {
            setFormalizacionIniciada(false)
            setPasoActual(11)
          }}
          onFormalizar={() => setFormalizacionIniciada(true)}
        />
      )
    }

    const pasoFuturo = pasosFuturos[pasoActual]

    return (
      <section className="flujo-originacion__pendiente">
        <span aria-hidden="true">{String(pasoActual).padStart(2, '0')}</span>
        <p>Originación · Paso {pasoActual} de 12</p>
        <h1>{pasoFuturo?.titulo ?? 'En construcción'}</h1>
        <p>
          {pasoFuturo?.detalle ??
            'Esta pantalla está lista para integrar su contenido.'}
        </p>
        <details>
          <summary>
            Ver contexto de la solicitud ({Object.keys(contexto).length}{' '}
            bloques)
          </summary>
          <pre>{JSON.stringify(contexto, null, 2)}</pre>
        </details>
        <div className="flujo-originacion__acciones">
          <button
            type="button"
            onClick={() =>
              setPasoActual(
                (actual) => Math.max(1, actual - 1) as PasoOriginacion,
              )
            }
          >
            Volver al paso anterior
          </button>
          <button type="button" onClick={reiniciar}>
            Reiniciar originación
          </button>
        </div>
      </section>
    )
  }

  return <main className="flujo-originacion">{renderPasoActual()}</main>
}

export default FlujoOriginacion
