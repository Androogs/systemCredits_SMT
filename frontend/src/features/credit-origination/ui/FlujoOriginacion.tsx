import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  Clock3,
  FilePen,
  History,
  Info,
  RotateCcw,
  ShieldCheck,
  UserRound,
} from 'lucide-react'
import AutorizacionDatos from './AutorizacionDatos'
import { CapturaEvidencia, DatosYPoliticas } from './EvidenciaYDatos'
import RechazoPoliticas from './RechazoPoliticas'
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
import {
  etapasOriginacion,
  type PasoOriginacion,
} from '../model/etapas-originacion'
import {
  normalizarFecha,
  tipoDocumentoUi,
  type IdentidadSolicitante,
} from '../model/mapeos-api'
import {
  listarEvidenciasSolicitud,
  obtenerSolicitud,
} from '../api/originacionApi'
import { pasoParaRetomar } from '../model/retomar'
import {
  numero,
  OCUPACION_LABELS,
} from '../../../entities/credit/model/solicitudesPanel'
import type { DatosSolicitud } from './CrearSolicitud'
import { tituloPagina } from '../../../shared/lib/marca'
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
  // La cédula confirmada en el paso 3 (datos y políticas) es la fuente de
  // verdad; aquí quedan solo dígitos.
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
    mesesContinuidad: laborales?.meses_continuidad ?? null,
    aniosCamara: numero(laborales?.anios_camara_comercio),
    ingresosMensuales: numero(laborales?.ingreso_mensual) ?? null,
    entidadPagadora: '',
  }
  return {
    idSolicitud: datos.id_solicitud,
    solicitud,
    validacion: {
      tipoDocumento: tipoDocumentoUi(datos.tipo_documento),
      numeroDocumento: datos.num_cedula,
      fechaNacimiento: datos.fecha_nacimiento ?? '',
      nacionalidad: 'Colombia',
      multasPendientes: false,
    },
    revision: {
      nombres: partes.slice(0, mitad).join(' '),
      apellidos: partes.slice(mitad).join(' '),
      numeroIdentificacion: datos.num_cedula,
      sexo: '',
      fechaNacimiento: datos.fecha_nacimiento ?? '',
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
  // desde el backend y aterriza en el primer paso que quedó pendiente
  // (autorización, evidencia/OCR, perfil económico o evaluación).
  const retomarId = (location.state as { retomarId?: string } | null)?.retomarId
  const [retomando, setRetomando] = useState(Boolean(retomarId))
  const [errorRetomar, setErrorRetomar] = useState<string | null>(null)

  const [pasoActual, setPasoActual] = useState<PasoOriginacion>(1)
  const [contexto, setContexto] = useState<ContextoOriginacion>(() =>
    simulacionRuta ? { simulacion: simulacionRuta } : {},
  )
  const [formalizacionIniciada, setFormalizacionIniciada] = useState(false)
  // Multas confirmadas en el paso 3: se radica la solicitud rechazada y
  // el proceso termina ('registrado' = ya persistida en el backend).
  const [cierrePoliticas, setCierrePoliticas] = useState<
    'pendiente' | 'registrado' | null
  >(null)
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
      // Las evidencias se consultan aparte: si el endpoint falla se
      // asume que no hay captura y el paso derivado cae en evidencia.
      Promise.all([
        obtenerSolicitud(retomarId),
        listarEvidenciasSolicitud(retomarId).catch(() => []),
      ])
        .then(([datos, evidencias]) => {
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
          setPasoActual(pasoParaRetomar(datos, evidencias))
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

    document.title = tituloPagina(title)
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
    if (formalizacionIniciada || cierrePoliticas === 'registrado') {
      limpiarBorrador()
      return
    }
    if (pasoActual === 1 && Object.keys(contexto).length === 0) return
    guardarBorrador(pasoActual, contexto, formalizacionIniciada)
  }, [
    pasoActual,
    contexto,
    formalizacionIniciada,
    borradorPendiente,
    cierrePoliticas,
  ])

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
    setCierrePoliticas(null)
  }

  // Rechazo confirmado: la solicitud ya quedó evaluada en el backend, así
  // que el proceso termina — se limpia el borrador (sin esto la pestaña
  // volvería a ofrecer "retomar") y se va al expediente de la solicitud.
  const finalizarProceso = () => {
    const id = contexto.idSolicitud
    reiniciar()
    if (id) {
      navigate(`/solicitudes/${id}`)
    }
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

    const paso = Math.min(5, Math.max(1, borradorPendiente!.paso))
    const estado = ctx.idSolicitud
      ? ctx.resultadoEvaluacion
        ? 'Evaluada'
        : 'Radicada'
      : 'Borrador local'

    return (
      <section className="flujo-originacion__pendiente retomar">
        <header className="retomar__cabecera">
          <span className="retomar__icono" aria-hidden="true">
            <History size={24} strokeWidth={2.1} />
          </span>
          <div className="retomar__cabecera-texto">
            <p className="retomar__eyebrow">
              <span className="retomar__pulso" aria-hidden="true" />
              Solicitud en curso
            </p>
            <h1>Retomar originación</h1>
          </div>
          <div className="retomar__avance" title={`Paso ${paso} de 5`}>
            <svg viewBox="0 0 40 40" aria-hidden="true">
              <circle
                className="retomar__avance-fondo"
                cx="20"
                cy="20"
                r="16"
              />
              <circle
                className="retomar__avance-relleno"
                cx="20"
                cy="20"
                r="16"
                pathLength={100}
                strokeDasharray={`${paso * 20} 100`}
              />
            </svg>
            <span>
              {paso}
              <small>/5</small>
            </span>
          </div>
        </header>

        <p className="retomar__descripcion">
          Hay una solicitud sin terminar de <strong>{nombre}</strong>. Tu avance
          está guardado en este dispositivo: continúa justo donde la dejaste o
          descártala para empezar de cero.
        </p>

        <div className="retomar__progreso">
          <div className="retomar__progreso-head">
            <span className="retomar__progreso-label">Avance guardado</span>
            <span className="retomar__progreso-paso">
              Paso <strong>{paso}</strong> de 5 ·{' '}
              {etapasOriginacion[paso - 1].titulo}
            </span>
          </div>
          <div
            className="retomar__barra"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={5}
            aria-valuenow={paso}
            aria-label="Progreso de la solicitud"
          >
            {etapasOriginacion.map((etapa, indice) => (
              <span
                key={etapa.titulo}
                className={
                  indice + 1 < paso
                    ? 'retomar__segmento retomar__segmento--hecho'
                    : indice + 1 === paso
                      ? 'retomar__segmento retomar__segmento--actual'
                      : 'retomar__segmento'
                }
              />
            ))}
          </div>
        </div>

        <ul className="retomar__meta">
          <li>
            <UserRound size={17} aria-hidden="true" />
            <div>
              <span>Solicitante</span>
              <strong>{nombre}</strong>
            </div>
          </li>
          <li>
            <Clock3 size={17} aria-hidden="true" />
            <div>
              <span>Último guardado</span>
              <strong>{hora || 'Sin registrar'}</strong>
            </div>
          </li>
          <li>
            {ctx.idSolicitud ? (
              <ShieldCheck size={17} aria-hidden="true" />
            ) : (
              <FilePen size={17} aria-hidden="true" />
            )}
            <div>
              <span>Estado</span>
              <strong>{estado}</strong>
            </div>
          </li>
        </ul>

        {ctx.idSolicitud ? (
          <p className="retomar__nota">
            <Info size={15} aria-hidden="true" />
            {ctx.resultadoEvaluacion
              ? 'La solicitud ya fue evaluada; retomarás el resultado y la oferta.'
              : 'La solicitud ya fue radicada en el sistema; puedes continuar desde la evaluación.'}
          </p>
        ) : null}

        <div className="retomar__acciones">
          <button
            type="button"
            className="retomar__btn retomar__btn--primario"
            onClick={retomarBorrador}
          >
            Continuar donde quedó
            <ArrowRight size={16} aria-hidden="true" />
          </button>
          <button
            type="button"
            className="retomar__btn retomar__btn--secundario"
            onClick={descartarBorrador}
          >
            <RotateCcw size={15} aria-hidden="true" />
            Descartar y empezar de cero
          </button>
        </div>
      </section>
    )
  }

  const renderPasoActual = () => {
    if (cierrePoliticas) {
      return (
        <RechazoPoliticas
          identidad={identidadDesdeContexto(contexto)}
          sesionCapturaToken={contexto.biometria?.sesionToken}
          onRegistrada={() => setCierrePoliticas('registrado')}
          onNuevaSolicitud={reiniciar}
          onVolverSolicitudes={() => {
            reiniciar()
            navigate('/solicitudes')
          }}
          onBack={() => setCierrePoliticas(null)}
        />
      )
    }

    if (pasoActual === 1) {
      return (
        <AutorizacionDatos
          onContinue={(autorizacion) => {
            setContexto((actual) => ({ ...actual, autorizacion }))
            setPasoActual(2)
          }}
        />
      )
    }

    // Sin captura previa (p. ej. borrador guardado justo antes del QR) el
    // paso 3 no tiene OCR que revisar: se vuelve a la captura.
    if (pasoActual === 2 || (pasoActual === 3 && !contexto.biometria)) {
      // Al retomar una solicitud ya hay cédula/nombre conocidos: el OCR
      // los compara. En un flujo nuevo aún no hay nada digitado.
      const { validacion, revision } = contexto
      return (
        <CapturaEvidencia
          datosEsperados={{
            ...(revision?.nombres ? { nombres: revision.nombres } : {}),
            ...(revision?.apellidos ? { apellidos: revision.apellidos } : {}),
            ...(validacion?.numeroDocumento
              ? { numero_documento: validacion.numeroDocumento }
              : {}),
            ...(validacion?.fechaNacimiento
              ? { fecha_nacimiento: validacion.fechaNacimiento }
              : {}),
          }}
          onBack={() => setPasoActual(1)}
          onContinue={(biometria) => {
            setContexto((actual) => ({ ...actual, biometria }))
            setPasoActual(3)
          }}
        />
      )
    }

    if (pasoActual === 3 && contexto.biometria) {
      return (
        <DatosYPoliticas
          biometria={contexto.biometria}
          revisionPrevia={contexto.revision}
          validacionPrevia={contexto.validacion}
          onBack={() => setPasoActual(2)}
          onContinue={({ ocr, revision, validacion }) => {
            setContexto((actual) => ({ ...actual, ocr, revision, validacion }))
            if (validacion.multasPendientes) {
              setCierrePoliticas('pendiente')
            } else {
              setPasoActual(4)
            }
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
          idSolicitud={contexto.idSolicitud}
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
          onFinalizar={finalizarProceso}
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
