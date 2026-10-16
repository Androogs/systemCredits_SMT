import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import ValidacionInicial from './ValidacionInicial'
import AutorizacionDatos from './AutorizacionDatos'
import EvidenciaYDatos from './EvidenciaYDatos'
import CrearSolicitud, { type ResultadoCrearSolicitud } from './CrearSolicitud'
import EvaluacionYResultado from './EvaluacionYResultado'
import {
  type BorradorOriginacion,
  type ContextoOriginacion,
  type SimulacionPrevia,
  cargarBorrador,
  guardarBorrador,
  limpiarBorrador,
} from '../model/borrador'
import type { PasoOriginacion } from '../model/etapas-originacion'
import {
  normalizarFecha,
  tipoDocumentoUi,
  type IdentidadSolicitante,
} from '../model/mapeos-api'
import { obtenerSolicitud } from '../api/originacionApi'
import {
  numero,
  OCUPACION_LABELS,
} from '../../../entities/credit/model/solicitudesPanel'
import type { DatosSolicitud } from './CrearSolicitud'
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
  // Basta con documento + nombre: en una solicitud retomada el nombre
  // completo llega sin separar en nombres/apellidos.
  if (!validacion || !revision?.nombres.trim()) {
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
    telefono: contexto.autorizacion?.telefono,
    correo: contexto.autorizacion?.correo,
    autorizoHabeas: contexto.autorizacion?.autorizaTratamiento === true,
    fechaExpedicion: revision.fechaExpedicion,
    ciudadExpedicion: revision.ciudadExpedicion,
    lugarNacimiento: revision.lugarNacimiento,
  }
}

/** Reconstruye el contexto del paso 5 desde una solicitud persistida. */
function contextoDesdeSolicitud(
  datos: Awaited<ReturnType<typeof obtenerSolicitud>>,
): ContextoOriginacion {
  // El backend expone el nombre completo sin separar: se reparte por la
  // mitad como aproximación nombres/apellidos (convención colombiana).
  const partes = datos.nombre_cliente.trim().split(/\s+/)
  const mitad = Math.ceil(partes.length / 2)
  const laborales = datos.datos_laborales
  const solicitud: DatosSolicitud = {
    lineaCredito: datos.linea_credito ?? 'Inversiones Pacífico',
    destinoCredito: datos.destino_credito ?? 'Financiamiento de Vehículos',
    plazoMeses: datos.plazo_deseado_meses ?? 24,
    ocupacion: OCUPACION_LABELS[datos.ocupacion ?? ''] ?? datos.ocupacion ?? '',
    tipoContrato: laborales?.tipo_contrato ?? '',
    subtipoIndependiente: '',
    empresa: '',
    mesesContinuidad: laborales?.meses_continuidad ?? 0,
    aniosCamara: numero(laborales?.anios_camara_comercio),
    ingresosMensuales: numero(laborales?.ingreso_mensual) ?? 0,
    entidadPagadora: '',
  }
  return {
    idSolicitud: datos.id_solicitud,
    solicitud,
    validacion: {
      tipoDocumento: tipoDocumentoUi(datos.tipo_documento),
      numeroDocumento: datos.num_cedula,
      edad: 0,
      nacionalidad: 'Colombia',
      multasPendientes: false,
    },
    revision: {
      nombres: partes.slice(0, mitad).join(' '),
      apellidos: partes.slice(mitad).join(' '),
      numeroIdentificacion: datos.num_cedula,
      sexo: '',
      fechaNacimiento: '',
      lugarNacimiento: '',
      fechaExpedicion: '',
      ciudadExpedicion: '',
    },
  }
}

function FlujoOriginacion() {
  const location = useLocation()
  const navigate = useNavigate()
  // El simulador llega por state de ruta; se siembra en el contexto (el
  // autoguardado del borrador lo mantiene) y se limpia la ruta para que
  // un refresh o un "volver" no lo reinyecte.
  const simulacionRuta = (
    location.state as { simulacion?: SimulacionPrevia } | null
  )?.simulacion
  // "Continuar" desde la lista de solicitudes: reconstruye el contexto
  // desde el backend y aterriza en el paso 5 (evaluación y oferta).
  const retomarId = (location.state as { retomarId?: string } | null)?.retomarId
  const [retomando, setRetomando] = useState(Boolean(retomarId))
  const [errorRetomar, setErrorRetomar] = useState<string | null>(null)

  const [pasoActual, setPasoActual] = useState<PasoOriginacion>(1)
  const [contexto, setContexto] = useState<ContextoOriginacion>(() =>
    simulacionRuta ? { simulacion: simulacionRuta } : {},
  )
  const [formalizacionIniciada, setFormalizacionIniciada] = useState(false)
  // Borrador detectado al abrir el flujo: se muestra la opción de
  // retomar antes de guardar nada encima.
  const [borradorPendiente, setBorradorPendiente] =
    useState<BorradorOriginacion | null>(() => cargarBorrador())

  useEffect(() => {
    if (simulacionRuta || retomarId) {
      navigate(location.pathname, { replace: true, state: null })
    }
    if (retomarId) {
      let cancelado = false
      obtenerSolicitud(retomarId)
        .then((datos) => {
          if (cancelado) return
          // El borrador local es de otra solicitud: al retomar una
          // persistida se descarta y el autoguardado crea uno nuevo.
          limpiarBorrador()
          setBorradorPendiente(null)
          // Oferta ya seleccionada: la originación quedó cerrada; lo que
          // sigue es la formalización/desembolso en el detalle.
          if (
            datos.ofertas.some((o) => o.seleccionada) ||
            datos.estado === 'desembolsada'
          ) {
            navigate(`/solicitudes/${datos.id_solicitud}`, {
              replace: true,
            })
            return
          }
          setContexto(contextoDesdeSolicitud(datos))
          setPasoActual(5)
        })
        .catch(() => {
          if (!cancelado) {
            setErrorRetomar(
              'No se pudo recuperar la solicitud; revisa la conexión e intenta de nuevo.',
            )
          }
        })
        .finally(() => {
          if (!cancelado) setRetomando(false)
        })
      return () => {
        cancelado = true
      }
    }
    // Solo al montar: consumir el state de la ruta una vez.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

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
    setContexto(
      simulacionRuta
        ? { ...borradorPendiente.contexto, simulacion: simulacionRuta }
        : borradorPendiente.contexto,
    )
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

  const renderRetomando = () => (
    <section className="flujo-originacion__pendiente">
      <p>Originación</p>
      <h1>Recuperando solicitud…</h1>
      <p role="status">Cargando los datos persistidos de la solicitud.</p>
    </section>
  )

  const renderErrorRetomar = () => (
    <section className="flujo-originacion__pendiente">
      <p>Originación</p>
      <h1>No se pudo retomar</h1>
      <p role="alert">{errorRetomar}</p>
      <div className="flujo-originacion__acciones">
        <button type="button" onClick={reiniciar}>
          Empezar una solicitud nueva
        </button>
      </div>
    </section>
  )

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
          simulacion={contexto.simulacion}
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
      {retomando
        ? renderRetomando()
        : errorRetomar
          ? renderErrorRetomar()
          : borradorPendiente
            ? renderBorradorPendiente()
            : renderPasoActual()}
    </div>
  )
}

export default FlujoOriginacion
