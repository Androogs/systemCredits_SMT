import { useEffect, useState } from 'react'
import ValidacionInicial from './ValidacionInicial'
import AutorizacionDatos from './AutorizacionDatos'
import CapturaCedula from './CapturaCedula'
import ProcesamientoOCR from './ProcesamientoOCR'
import RevisionDatos from './RevisionDatos'
import ResultadoValidacion from './ResultadoValidacion'
import CrearSolicitud, { type ResultadoCrearSolicitud } from './CrearSolicitud'
import PreparacionConsulta from './PreparacionConsulta'
import ConsultaEnCurso from './ConsultaEnCurso'
import InformeCrediticio from './InformeCrediticio'
import EvaluacionIntegral from './EvaluacionIntegral'
import ResultadoCredito from './ResultadoCredito'
import { resultadoDesdeApi } from '../model/resultado-evaluacion'
import {
  construirEvaluacionPayload,
  primerApellido,
  type IdentidadSolicitante,
} from '../model/mapeos-api'
import { evaluarSolicitud } from '../api/originacionApi'
import {
  type BorradorOriginacion,
  type ContextoOriginacion,
  cargarBorrador,
  guardarBorrador,
  limpiarBorrador,
} from '../model/borrador'
import type { PasoOriginacion } from '../model/etapas-originacion'
import './FlujoOriginacion.css'

/**
 * Arma la identidad del solicitante con lo capturado en los pasos 1-6.
 * Devuelve null si falta el documento o el nombre, en cuyo caso la
 * solicitud queda en modo demostración.
 */
function identidadDesdeContexto(
  contexto: ContextoOriginacion,
): IdentidadSolicitante | null {
  const { validacion, revision } = contexto
  if (!validacion || !revision?.nombres.trim() || !revision.apellidos.trim()) {
    return null
  }
  // La cédula digitada en el paso 1 es la fuente de verdad: el OCR y la
  // revisión la propagan ya formateada; aquí quedan solo dígitos.
  return {
    tipoDocumento: validacion.tipoDocumento,
    numeroDocumento: (
      revision.numeroIdentificacion || validacion.numeroDocumento
    ).replace(/\D/g, ''),
    nombres: revision.nombres,
    apellidos: revision.apellidos,
    fechaNacimiento: normalizarFecha(revision.fechaNacimiento),
    nacionalidad: validacion.nacionalidad,
  }
}

/** Acepta 'YYYY-MM-DD' o 'DD/MM/YYYY' y devuelve formato ISO. */
function normalizarFecha(valor: string): string {
  const texto = valor.trim()
  if (/^\d{4}-\d{2}-\d{2}$/.test(texto)) return texto
  const ddmmyyyy = /^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$/.exec(texto)
  if (ddmmyyyy) {
    const [, dia, mes, anio] = ddmmyyyy
    return `${anio}-${mes.padStart(2, '0')}-${dia.padStart(2, '0')}`
  }
  return texto
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
  // Borrador detectado al abrir el flujo: se muestra la opción de
  // retomar antes de guardar nada encima.
  const [borradorPendiente, setBorradorPendiente] =
    useState<BorradorOriginacion | null>(() => cargarBorrador())

  // Autoguardado local: cada avance de paso o cambio de contexto queda
  // persistido, de modo que cerrar el navegador o perder energía no
  // pierde el proceso. No se guarda mientras un borrador previo está
  // pendiente de decisión (retomar/descartar), y una vez iniciada la
  // formalización la solicitud ya vive en el backend.
  useEffect(() => {
    if (borradorPendiente) return
    if (formalizacionIniciada) {
      limpiarBorrador()
      return
    }
    if (pasoActual === 1 && Object.keys(contexto).length === 0) return
    guardarBorrador(pasoActual, contexto, formalizacionIniciada)
  }, [pasoActual, contexto, formalizacionIniciada, borradorPendiente])

  const retomarBorrador = () => {
    if (!borradorPendiente) return
    setContexto(borradorPendiente.contexto)
    setFormalizacionIniciada(borradorPendiente.formalizacionIniciada)
    setPasoActual(
      Math.min(12, Math.max(1, borradorPendiente.paso)) as PasoOriginacion,
    )
    setBorradorPendiente(null)
  }

  const descartarBorrador = () => {
    limpiarBorrador()
    setBorradorPendiente(null)
  }

  const reiniciar = () => {
    limpiarBorrador()
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

  const renderBorradorPendiente = () => {
    const ctx = borradorPendiente!.contexto
    const nombre =
      `${ctx.revision?.nombres ?? ''} ${ctx.revision?.apellidos ?? ''}`.trim() ||
      ctx.consulta?.nombreCompleto ||
      `Documento ${ctx.validacion?.numeroDocumento ?? ''}`.trim()
    const guardado = new Date(borradorPendiente!.guardadoEn)
    const hora = Number.isNaN(guardado.getTime())
      ? ''
      : guardado.toLocaleString('es-CO', {
          dateStyle: 'medium',
          timeStyle: 'short',
        })

    return (
      <section className="flujo-originacion__pendiente">
        <span aria-hidden="true">
          {String(borradorPendiente!.paso).padStart(2, '0')}
        </span>
        <p>Solicitud en curso</p>
        <h1>Retomar originación</h1>
        <p>
          Hay una solicitud sin terminar de <strong>{nombre}</strong> guardada
          en el paso {borradorPendiente!.paso} de 12
          {hora ? ` (${hora})` : ''}.
          {ctx.idSolicitud
            ? ' La solicitud ya fue radicada en el sistema; puedes continuar desde la evaluación.'
            : ''}
        </p>
        <div className="flujo-originacion__acciones">
          <button type="button" onClick={retomarBorrador}>
            Continuar donde quedó
          </button>
          <button type="button" onClick={descartarBorrador}>
            Descartar y empezar de cero
          </button>
        </div>
      </section>
    )
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
          numeroDocumento={contexto.validacion?.numeroDocumento}
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
          inicial={
            contexto.revision ?? {
              numeroIdentificacion:
                contexto.ocr?.numeroDocumento ??
                contexto.validacion?.numeroDocumento,
              nombres: contexto.ocr?.nombres,
              apellidos: contexto.ocr?.apellidos,
            }
          }
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
          identidad={identidadDesdeContexto(contexto) ?? undefined}
          onContinue={(creada: ResultadoCrearSolicitud) => {
            setContexto((actual) => ({
              ...actual,
              solicitud: creada.datos,
              idSolicitud: creada.idSolicitud,
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
          inicial={
            contexto.consulta ?? {
              nombreCompleto:
                `${contexto.revision?.nombres ?? ''} ${contexto.revision?.apellidos ?? ''}`.trim() ||
                undefined,
              numeroDocumento: contexto.revision?.numeroIdentificacion,
              autorizacionFecha: contexto.autorizacion?.fechaRegistro,
              autorizacionIp: contexto.autorizacion?.ipAsesor,
            }
          }
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
          ejecutarConsulta={
            contexto.idSolicitud && contexto.solicitud
              ? () =>
                  evaluarSolicitud(
                    contexto.idSolicitud!,
                    construirEvaluacionPayload(
                      contexto.solicitud!,
                      {
                        origen: contexto.consulta?.origen ?? 'demo',
                        escenarioMock:
                          contexto.consulta?.escenarioMock ?? 'aprobado',
                      },
                      {
                        primerApellido: contexto.revision?.apellidos
                          ? primerApellido(contexto.revision.apellidos)
                          : undefined,
                        tieneMultasRunt:
                          contexto.validacion?.multasPendientes ?? false,
                      },
                    ),
                  ).then((respuesta) =>
                    resultadoDesdeApi(
                      respuesta,
                      contexto.solicitud!.plazoMeses,
                    ),
                  )
              : undefined
          }
          onBack={() => setPasoActual(8)}
          onContinue={(resultadoConsulta, evaluacion) => {
            setContexto((actual) => ({
              ...actual,
              resultadoConsulta,
              resultadoEvaluacion: evaluacion ?? actual.resultadoEvaluacion,
            }))
            setPasoActual(10)
          }}
        />
      )
    }

    if (pasoActual === 10) {
      return (
        <InformeCrediticio
          resultado={contexto.resultadoEvaluacion}
          onModificarDatos={modificarSolicitud}
          onContinue={() => setPasoActual(11)}
        />
      )
    }

    if (pasoActual === 11) {
      return (
        <EvaluacionIntegral
          solicitud={contexto.solicitud}
          resultadoPrevio={contexto.resultadoEvaluacion}
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
          idSolicitud={contexto.idSolicitud}
          formalizacionIniciada={formalizacionIniciada}
          onModificar={() => {
            setFormalizacionIniciada(false)
            setPasoActual(11)
          }}
          onFormalizar={(ofertaSeleccionada) => {
            setContexto((actual) => ({ ...actual, ofertaSeleccionada }))
            setFormalizacionIniciada(true)
          }}
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

  return (
    <main className="flujo-originacion">
      {borradorPendiente ? renderBorradorPendiente() : renderPasoActual()}
    </main>
  )
}

export default FlujoOriginacion
