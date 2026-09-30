import { useEffect, useRef, useState } from 'react'
import './ProcesamientoOCR.css'

export interface ResultadoOCR {
  numeroDocumento: string
  nombres: string
  apellidos: string
  fechaExpedicion: string
  vigente: boolean
  calidadImagen: 'aprobada' | 'rechazada'
  alteraciones: boolean
}

interface ProcesamientoOCRProps {
  onContinue?: (resultado: ResultadoOCR) => void
  onBack?: () => void
  /** Si es true, simula el procesamiento automáticamente al montar. */
  autoStart?: boolean
}

const pasos = [
  {
    number: '01',
    label: 'Validación Inicial',
    detail: 'Datos básicos y filtros',
  },
  {
    number: '02',
    label: 'Tratamiento de Datos',
    detail: 'Habeas data y consentimiento',
  },
  {
    number: '03',
    label: 'Captura de Cédula',
    detail: 'Anverso y reverso de ID',
  },
  {
    number: '04',
    label: 'Procesamiento OCR',
    detail: 'Extracción y biometría',
  },
  {
    number: '05',
    label: 'Verificación de Datos',
    detail: 'Confirmación de campos',
  },
  {
    number: '06',
    label: 'Resultado Validación',
    detail: 'Resumen y radicación',
  },
] as const

const PASO_ACTUAL = 4

type EstadoTarea = 'pendiente' | 'en-proceso' | 'completada'

interface Tarea {
  id: string
  label: string
  detalle: string
}

const tareas: Tarea[] = [
  {
    id: 'calidad',
    label: 'Calidad de imagen aprobada',
    detalle: 'Enfoque, iluminación y bordes verificados',
  },
  {
    id: 'extraccion',
    label: 'Extracción de campos básicos',
    detalle: 'Nombres, número y fecha de expedición',
  },
  {
    id: 'registraduria',
    label: 'Validación cruzada con Registraduría',
    detalle: 'Consulta al servicio oficial de identificación',
  },
  {
    id: 'vigencia',
    label: 'Verificación de vigencia del documento',
    detalle: 'Estado actual y detector de alteraciones',
  },
]

/**
 * Simulación del pipeline OCR: cada tarea toma ~900 ms.
 * En producción reemplaza por llamadas al backend y actualiza el estado
 * con la respuesta real.
 */
function ProcesamientoOCR({
  onContinue,
  onBack,
  autoStart = true,
}: ProcesamientoOCRProps) {
  const [estadoTareas, setEstadoTareas] = useState<Record<string, EstadoTarea>>(
    () => Object.fromEntries(tareas.map((t) => [t.id, 'pendiente'])),
  )
  const [progreso, setProgreso] = useState(0)
  const [completado, setCompletado] = useState(false)
  const [reinicio, setReinicio] = useState(0)
  const timeoutRef = useRef<number | null>(null)

  // Orquesta la simulación paso a paso
  useEffect(() => {
    if (!autoStart) return

    let cancelado = false
    let indice = 0

    const avanzar = () => {
      if (cancelado) return

      if (indice >= tareas.length) {
        setProgreso(100)
        setCompletado(true)
        return
      }

      const tarea = tareas[indice]
      setEstadoTareas((prev) => ({ ...prev, [tarea.id]: 'en-proceso' }))

      timeoutRef.current = window.setTimeout(() => {
        if (cancelado) return
        setEstadoTareas((prev) => ({ ...prev, [tarea.id]: 'completada' }))
        setProgreso(Math.round(((indice + 1) / tareas.length) * 100))
        indice += 1
        avanzar()
      }, 900)
    }

    avanzar()

    return () => {
      cancelado = true
      if (timeoutRef.current) window.clearTimeout(timeoutRef.current)
    }
  }, [autoStart, reinicio])

  const reiniciar = () => {
    if (timeoutRef.current) window.clearTimeout(timeoutRef.current)
    setEstadoTareas(Object.fromEntries(tareas.map((t) => [t.id, 'pendiente'])))
    setProgreso(0)
    setCompletado(false)
    setReinicio((n) => n + 1)
  }

  const handleContinuar = () => {
    onContinue?.({
      numeroDocumento: '1.032.448.900',
      nombres: 'CARLOS MARIO',
      apellidos: 'MENDOZA',
      fechaExpedicion: 'Palmira (Valle)',
      vigente: true,
      calidadImagen: 'aprobada',
      alteraciones: false,
    })
  }

  const tareaActual = tareas.find((t) => estadoTareas[t.id] === 'en-proceso')
  const tituloEstado = completado
    ? 'Procesamiento completado'
    : tareaActual
      ? `${tareaActual.label}…`
      : 'Iniciando procesamiento…'

  return (
    <div className="ocr">
      <header className="ocr__header">
        <div className="ocr__header-copy">
          <p className="ocr__eyebrow">Originación Individual · Paso 4</p>
          <h1>Procesamiento OCR y Biométrica</h1>
          <p className="ocr__subtitle">Análisis del Documento Digital</p>
          <p className="ocr__lede">
            Procesando el documento mediante el motor OCR y verificando contra
            bases de datos oficiales.
          </p>
        </div>

        <aside className="ocr__panel" aria-label="Contexto de la radicación">
          <dl className="ocr__meta">
            <div>
              <dt>Asesor</dt>
              <dd>Carlos Mendoza</dd>
            </div>
            <div>
              <dt>Sede</dt>
              <dd>Palmira - Centro Interno</dd>
            </div>
          </dl>
          <span className="ocr__server">
            <span aria-hidden="true" />
            Servidor de Validación Activo v2.4.12-Prod (SSL)
          </span>
        </aside>
      </header>

      <ol className="ocr__steps" aria-label="Etapas del proceso de originación">
        {pasos.map((paso, indice) => {
          const posicion = indice + 1
          const estado =
            posicion < PASO_ACTUAL
              ? 'is-done'
              : posicion === PASO_ACTUAL
                ? 'is-active'
                : 'is-pending'

          return (
            <li
              key={paso.number}
              className={`ocr__step ${estado}`}
              aria-current={posicion === PASO_ACTUAL ? 'step' : undefined}
            >
              <span className="ocr__step-number" aria-hidden="true">
                {posicion < PASO_ACTUAL ? '✓' : paso.number}
              </span>
              <span className="ocr__step-copy">
                <strong>{paso.label}</strong>
                <small>{paso.detail}</small>
              </span>
            </li>
          )
        })}
      </ol>

      <div className="ocr__grid">
        {/* Columna izquierda: estado del procesamiento */}
        <section
          className="ocr__card ocr__card--estado"
          aria-live="polite"
          aria-label="Estado del procesamiento"
        >
          <header className="ocr__card-head">
            <div>
              <h2>Estado del Procesamiento</h2>
              <p
                className={`ocr__estado-titulo${completado ? ' is-done' : ''}`}
              >
                {tituloEstado}
              </p>
            </div>
            <span className={`ocr__porcentaje${completado ? ' is-done' : ''}`}>
              {progreso}%
            </span>
          </header>

          <div
            className="ocr__progress"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progreso}
            aria-label="Progreso del procesamiento OCR"
          >
            <span
              className={`ocr__progress-bar${completado ? ' is-done' : ''}`}
              style={{ width: `${progreso}%` }}
            />
          </div>

          <ul className="ocr__tasks">
            {tareas.map((tarea, indice) => {
              const estado = estadoTareas[tarea.id]
              return (
                <li
                  key={tarea.id}
                  className={`ocr__task ocr__task--${estado}`}
                  aria-current={estado === 'en-proceso' ? 'step' : undefined}
                >
                  <span className="ocr__task-icon" aria-hidden="true">
                    {estado === 'completada' && (
                      <svg viewBox="0 0 24 24" focusable="false">
                        <path
                          d="M5 12.5 10 17l9-10"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2.6"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    )}
                    {estado === 'en-proceso' && (
                      <span className="ocr__task-spinner" />
                    )}
                    {estado === 'pendiente' && (
                      <span className="ocr__task-number">{indice + 1}</span>
                    )}
                  </span>
                  <span className="ocr__task-copy">
                    <strong>{tarea.label}</strong>
                    <small>{tarea.detalle}</small>
                  </span>
                </li>
              )
            })}
          </ul>

          {completado && (
            <div className="ocr__banner" role="status">
              <strong>Documento validado correctamente.</strong>
              <span>
                Detector de alteraciones activo · Sin hallazgos · Puedes
                continuar a la verificación de datos.
              </span>
            </div>
          )}
        </section>

        {/* Columna derecha: vista previa del documento */}
        <section
          className="ocr__card ocr__card--preview"
          aria-label="Vista previa del documento detectado"
        >
          <h2 className="ocr__preview-title">
            Vista previa del documento detectado
          </h2>

          <div
            className="ocr__doc"
            role="img"
            aria-label="Cédula de ciudadanía detectada"
          >
            <span className="ocr__doc-chip" aria-hidden="true" />
            <p className="ocr__doc-country">República de Colombia</p>
            <p className="ocr__doc-type">Cédula de Ciudadanía</p>

            <div className="ocr__doc-body">
              <div className="ocr__doc-photo" aria-hidden="true" />
              <div className="ocr__doc-fields">
                <div className="ocr__doc-field">
                  <span>Número / Number</span>
                  <strong>1.032.448.900</strong>
                </div>
                <div className="ocr__doc-field">
                  <span>Nombres / Names</span>
                  <strong>CARLOS MARIO</strong>
                </div>
              </div>
            </div>

            {completado && (
              <span className="ocr__doc-verified" aria-hidden="true">
                <svg viewBox="0 0 24 24" focusable="false">
                  <path
                    d="M5 12.5 10 17l9-10"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.6"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                Verificado
              </span>
            )}
          </div>

          <div className="ocr__detector">
            <span className="ocr__detector-dot" aria-hidden="true" />
            Detector de alteraciones activo
          </div>
        </section>
      </div>

      <div className="ocr__actions">
        <div className="ocr__actions-left">
          {onBack && (
            <button className="ocr__back" type="button" onClick={onBack}>
              ← Volver al paso anterior
            </button>
          )}
          {!completado ? (
            <p className="ocr__actions-note">
              <span className="ocr__dot ocr__dot--live" aria-hidden="true" />
              Procesando · no cierres esta ventana
            </p>
          ) : (
            <p className="ocr__actions-note">
              <span className="ocr__dot" aria-hidden="true" />
              Listo para continuar
            </p>
          )}
        </div>

        <div className="ocr__actions-right">
          {completado && (
            <button
              className="ocr__secondary"
              type="button"
              onClick={reiniciar}
            >
              Reprocesar
            </button>
          )}
          <button
            className="ocr__submit"
            type="button"
            onClick={handleContinuar}
            disabled={!completado}
          >
            Continuar a Verificación
          </button>
        </div>
      </div>
    </div>
  )
}

export default ProcesamientoOCR
