import { useEffect, useRef, useState } from 'react'
import { Check, CircleAlert, LoaderCircle, RotateCcw } from 'lucide-react'
import type { ResultadoEvaluacionCredito } from '../model/resultado-evaluacion'
import SeguimientoOriginacion from './SeguimientoOriginacion/SeguimientoOriginacion'
import './ConsultaEnCurso.css'

export interface ResultadoConsultaEnCurso {
  canal: 'principal' | 'secundario'
  reintentos: number
  finalizadaEn: string
}

interface ConsultaEnCursoProps {
  solicitante?: string
  /**
   * Consulta real al backend (creación + evaluación de la solicitud).
   * Si no se pasa, el paso queda en modo demostración.
   */
  ejecutarConsulta?: () => Promise<ResultadoEvaluacionCredito>
  onContinue?: (
    resultado: ResultadoConsultaEnCurso,
    evaluacion?: ResultadoEvaluacionCredito,
  ) => void
  onBack?: () => void
}

interface TareaConsulta {
  titulo: string
  detalle: string
}

const tareas: TareaConsulta[] = [
  {
    titulo: 'Validación de identidad local y primer apellido aprobada',
    detalle: 'Documento y coincidencia de identidad verificados',
  },
  {
    titulo: 'Conexión segura establecida con Datacrédito',
    detalle: 'Canal cifrado SSL disponible',
  },
  {
    titulo: 'Recuperando historial consolidado y comportamiento de pago',
    detalle: 'Consulta de obligaciones y novedades crediticias',
  },
  {
    titulo: 'Cálculo de indicadores y aplicación de políticas de riesgo',
    detalle: 'Preparación del informe para la siguiente etapa',
  },
]

function ConsultaEnCurso({
  solicitante,
  ejecutarConsulta,
  onContinue,
  onBack,
}: ConsultaEnCursoProps) {
  const [progreso, setProgreso] = useState(65)
  const [tareaActiva, setTareaActiva] = useState(2)
  const [completada, setCompletada] = useState(false)
  const [canal, setCanal] = useState<'principal' | 'secundario'>('principal')
  const [reintentos, setReintentos] = useState(0)
  const [resultadoApi, setResultadoApi] =
    useState<ResultadoEvaluacionCredito | null>(null)
  const [errorApi, setErrorApi] = useState<string | null>(null)
  const [consultando, setConsultando] = useState(false)
  const consultaDisparada = useRef(false)

  useEffect(() => {
    if (completada) return

    const recuperarHistorial = window.setTimeout(() => {
      setProgreso(86)
      setTareaActiva(3)
    }, 1800)
    const finalizarConsulta = window.setTimeout(() => {
      setProgreso(100)
      setTareaActiva(tareas.length)
      setCompletada(true)
    }, 4200)

    return () => {
      window.clearTimeout(recuperarHistorial)
      window.clearTimeout(finalizarConsulta)
    }
  }, [canal, completada, reintentos])

  const dispararConsulta = () => {
    if (!ejecutarConsulta) return
    setConsultando(true)
    setErrorApi(null)
    ejecutarConsulta()
      .then(setResultadoApi)
      .catch(() =>
        setErrorApi(
          'La evaluación en el backend no respondió. Puedes reintentar o continuar en modo demostración.',
        ),
      )
      .finally(() => setConsultando(false))
  }

  useEffect(() => {
    if (!consultaDisparada.current && ejecutarConsulta) {
      consultaDisparada.current = true
      dispararConsulta()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const reintentarCanalSecundario = () => {
    if (canal === 'secundario' && !completada) return
    setCanal('secundario')
    setCompletada(false)
    setProgreso(35)
    setTareaActiva(0)
    setReintentos((actuales) => actuales + 1)
  }

  const continuar = () => {
    if (!completada) return
    onContinue?.(
      {
        canal,
        reintentos,
        finalizadaEn: new Date().toISOString(),
      },
      resultadoApi ?? undefined,
    )
  }

  return (
    <div className="consulta-curso">
      <header className="consulta-curso__encabezado">
        <div>
          <p className="consulta-curso__eyebrow">
            Originación Individual · Paso 9
          </p>
          <h1>
            {completada
              ? 'Consulta crediticia completada'
              : 'Estableciendo conexión externa...'}
          </h1>
          <p className="consulta-curso__descripcion">
            {completada
              ? 'La simulación terminó. El informe está listo para continuar.'
              : 'Simulación de consulta a Datacrédito. No cierres esta ventana durante el procesamiento.'}
          </p>
        </div>

        <aside className="consulta-curso__contexto">
          <dl>
            <div>
              <dt>Asesor</dt>
              <dd>Carlos Mendoza</dd>
            </div>
            <div>
              <dt>Sede</dt>
              <dd>Palmira - Centro Interno</dd>
            </div>
            {solicitante && (
              <div>
                <dt>Solicitante</dt>
                <dd>{solicitante}</dd>
              </div>
            )}
          </dl>
          <span className="consulta-curso__modo">
            <span aria-hidden="true" />
            {ejecutarConsulta
              ? resultadoApi
                ? ' Evaluación real · Motor integrado'
                : ' Consultando motor integrado…'
              : ' Modo de demostración'}
          </span>
        </aside>
      </header>

      <SeguimientoOriginacion pasoActual={9} />

      <section
        className="consulta-curso__panel"
        aria-labelledby="consulta-curso-titulo"
        aria-live="polite"
      >
        <header className="consulta-curso__panel-encabezado">
          <h2 id="consulta-curso-titulo">Consultando historial financiero</h2>
          <strong>{progreso}% completado</strong>
        </header>

        <div
          className="consulta-curso__barra"
          role="progressbar"
          aria-label="Progreso de la consulta crediticia simulada"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={progreso}
        >
          <span style={{ width: `${progreso}%` }} />
        </div>

        <ol className="consulta-curso__tareas">
          {tareas.map((tarea, indice) => {
            const estado =
              indice < tareaActiva
                ? 'completada'
                : indice === tareaActiva && !completada
                  ? 'activa'
                  : 'pendiente'

            return (
              <li
                className={`consulta-curso__tarea consulta-curso__tarea--${estado}`}
                key={tarea.titulo}
                aria-current={estado === 'activa' ? 'step' : undefined}
              >
                <span className="consulta-curso__icono" aria-hidden="true">
                  {estado === 'completada' ? (
                    <Check size={14} strokeWidth={2.5} />
                  ) : estado === 'activa' ? (
                    <LoaderCircle
                      size={15}
                      className="consulta-curso__girando"
                    />
                  ) : (
                    String(indice + 1)
                  )}
                </span>
                <span className="consulta-curso__tarea-texto">
                  <strong>{tarea.titulo}</strong>
                  <small>{tarea.detalle}</small>
                </span>
              </li>
            )
          })}
        </ol>

        {completada && (
          <div className="consulta-curso__resultado" role="status">
            <Check size={17} aria-hidden="true" />
            {resultadoApi
              ? `Evaluación completada por el motor (${resultadoApi.auditoria}).`
              : consultando
                ? 'Consulta lista; esperando respuesta del motor…'
                : `Consulta finalizada por el canal ${canal}.`}
          </div>
        )}

        {errorApi && (
          <div className="consulta-curso__resultado" role="alert">
            <CircleAlert size={17} aria-hidden="true" />
            {errorApi}
            <button
              type="button"
              className="consulta-curso__reintentar"
              onClick={dispararConsulta}
              disabled={consultando}
            >
              <RotateCcw size={14} aria-hidden="true" />
              Reintentar
            </button>
          </div>
        )}
      </section>

      {!completada && (
        <aside className="consulta-curso__contingencia" role="note">
          <CircleAlert size={18} aria-hidden="true" />
          <div>
            <strong>Contingencia de conexión</strong>
            <p>
              En producción, el sistema podrá reintentar por un canal secundario
              autorizado sin exponer datos sensibles.
            </p>
          </div>
          <button
            className="consulta-curso__reintentar"
            type="button"
            onClick={reintentarCanalSecundario}
            disabled={canal === 'secundario'}
          >
            <RotateCcw size={15} aria-hidden="true" />
            {canal === 'secundario'
              ? 'Canal secundario activo'
              : 'Reintentar canal secundario'}
          </button>
        </aside>
      )}

      <footer className="consulta-curso__acciones">
        {onBack && (
          <button
            className="consulta-curso__volver"
            type="button"
            onClick={onBack}
            disabled={!completada}
          >
            Volver a preparación
          </button>
        )}
        <button
          className="consulta-curso__continuar"
          type="button"
          onClick={continuar}
          disabled={!completada || consultando}
        >
          {consultando
            ? 'Esperando al motor…'
            : 'Continuar al informe crediticio'}
        </button>
      </footer>
    </div>
  )
}

export default ConsultaEnCurso
