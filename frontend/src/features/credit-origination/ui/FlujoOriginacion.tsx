import { useEffect, useState } from 'react'
import ValidacionInicial from './ValidacionInicial'
import AutorizacionDatos from './AutorizacionDatos'
import EvidenciaYDatos from './EvidenciaYDatos'
import CrearSolicitud, { type ResultadoCrearSolicitud } from './CrearSolicitud'
import EvaluacionYResultado from './EvaluacionYResultado'
import {
  type BorradorOriginacion,
  type ContextoOriginacion,
  cargarBorrador,
  guardarBorrador,
  limpiarBorrador,
} from '../model/borrador'
import type { PasoOriginacion } from '../model/etapas-originacion'
import type { IdentidadSolicitante } from '../model/mapeos-api'
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

function FlujoOriginacion() {
  const [pasoActual, setPasoActual] = useState<PasoOriginacion>(1)
  const [contexto, setContexto] = useState<ContextoOriginacion>({})
  const [formalizacionIniciada, setFormalizacionIniciada] = useState(false)
  // Borrador detectado al abrir el flujo: se muestra la opción de
  // retomar antes de guardar nada encima.
  const [borradorPendiente, setBorradorPendiente] =
    useState<BorradorOriginacion | null>(() => cargarBorrador())

  useEffect(() => {
    const heading = document.querySelector<HTMLElement>('#main-content h1')
    const title = heading?.textContent?.trim()
    if (!heading || !title) return

    document.title = `${title} | Inversiones Pacífico`
    heading.tabIndex = -1
    heading.focus({ preventScroll: true })
  }, [pasoActual, borradorPendiente])

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
      Math.min(5, Math.max(1, borradorPendiente.paso)) as PasoOriginacion,
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
      delete contextoPrevio.resultadoEvaluacion
      delete contextoPrevio.ofertaSeleccionada
      return contextoPrevio
    })
    setFormalizacionIniciada(false)
    setPasoActual(4)
  }

  const renderBorradorPendiente = () => {
    const ctx = borradorPendiente!.contexto
    const nombre =
      `${ctx.revision?.nombres ?? ''} ${ctx.revision?.apellidos ?? ''}`.trim() ||
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
          en el paso {borradorPendiente!.paso} de 5{hora ? ` (${hora})` : ''}.
          {ctx.idSolicitud
            ? ctx.resultadoEvaluacion
              ? ' La solicitud ya fue evaluada; retomarás el resultado y la oferta.'
              : ' La solicitud ya fue radicada en el sistema; puedes continuar desde la evaluación.'
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
        <EvidenciaYDatos
          numeroDocumento={contexto.validacion?.numeroDocumento}
          onBack={() => setPasoActual(2)}
          onContinue={({ biometria, ocr, revision }) => {
            setContexto((actual) => ({ ...actual, biometria, ocr, revision }))
            setPasoActual(4)
          }}
        />
      )
    }

    if (pasoActual === 4) {
      return (
        <CrearSolicitud
          onBack={() => setPasoActual(3)}
          inicial={contexto.solicitud}
          identidad={identidadDesdeContexto(contexto) ?? undefined}
          sesionCapturaToken={contexto.biometria?.sesionToken}
          onContinue={(creada: ResultadoCrearSolicitud) => {
            setContexto((actual) => ({
              ...actual,
              solicitud: creada.datos,
              idSolicitud: creada.idSolicitud,
              resultadoEvaluacion: undefined,
            }))
            setPasoActual(5)
          }}
        />
      )
    }

    if (pasoActual === 5) {
      return (
        <EvaluacionYResultado
          idSolicitud={contexto.idSolicitud}
          solicitud={contexto.solicitud}
          identidad={identidadDesdeContexto(contexto) ?? undefined}
          validacion={contexto.validacion}
          resultadoInicial={contexto.resultadoEvaluacion ?? null}
          onBack={() => setPasoActual(4)}
          onModificar={modificarSolicitud}
          onResultado={(resultadoEvaluacion) =>
            setContexto((actual) => ({ ...actual, resultadoEvaluacion }))
          }
          onFormalizar={(ofertaSeleccionada) => {
            setContexto((actual) => ({ ...actual, ofertaSeleccionada }))
            // Proceso cerrado: el autoguardado borra el borrador y la
            // consulta ya no se puede reabrir para modificarla.
            setFormalizacionIniciada(true)
          }}
          onEnviadaEstudio={() => setFormalizacionIniciada(true)}
        />
      )
    }

    return (
      <section className="flujo-originacion__pendiente">
        <span aria-hidden="true">{String(pasoActual).padStart(2, '0')}</span>
        <p>Originación · Paso {pasoActual} de 5</p>
        <h1>En construcción</h1>
        <p>Esta pantalla está lista para integrar su contenido.</p>
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
    <div className="flujo-originacion">
      {borradorPendiente ? renderBorradorPendiente() : renderPasoActual()}
    </div>
  )
}

export default FlujoOriginacion
