import { useState } from 'react'
import './ResultadoValidacion.css'

export interface ResultadoFinal {
  identificador: string
  nodo: string
  aprobado: boolean
  advertencias: string[]
  creadoEn: string
}

interface ResultadoValidacionProps {
  onContinue?: (resultado: ResultadoFinal) => void
  onBack?: () => void
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

const PASO_ACTUAL = 6

type EstadoCriterio = 'cumple' | 'revisar' | 'no-cumple'

interface Criterio {
  id: string
  label: string
  valor: string
  estado: EstadoCriterio
}

const criterios: Criterio[] = [
  {
    id: 'edad',
    label: 'Rango de Edad (34 años)',
    valor: 'Cumple',
    estado: 'cumple',
  },
  {
    id: 'nacionalidad',
    label: 'Nacionalidad Colombiana',
    valor: 'Cumple',
    estado: 'cumple',
  },
  {
    id: 'multas',
    label: 'Estado de Multas en Tránsito',
    valor: 'Sin Pendientes',
    estado: 'cumple',
  },
  {
    id: 'ocr',
    label: 'Validación de Identidad por OCR',
    valor: 'Validada 98.4%',
    estado: 'cumple',
  },
  {
    id: 'habeas',
    label: 'Autorización de Habeas Data',
    valor: 'Firmada y auditada',
    estado: 'cumple',
  },
]

const identificador = 'VAL-HD-2026-883'
const nodo = 'Sede Bogotá Centro'

function ResultadoValidacion({ onContinue, onBack }: ResultadoValidacionProps) {
  const [creado, setCreado] = useState(false)
  const [enviando, setEnviando] = useState(false)

  const aprobado = criterios.every((c) => c.estado === 'cumple')

  const handleCrearSolicitud = () => {
    if (creado || enviando) return
    setEnviando(true)

    // Simulación de llamada al backend para radicar la solicitud.
    // En producción reemplaza esto por el POST real.
    window.setTimeout(() => {
      setEnviando(false)
      setCreado(true)
      onContinue?.({
        identificador,
        nodo,
        aprobado,
        advertencias: [
          'El cliente no tiene dirección física verificable en el documento.',
        ],
        creadoEn: new Date().toISOString(),
      })
    }, 900)
  }

  return (
    <div className="resultado">
      <header className="resultado__header">
        <div className="resultado__header-copy">
          <p className="resultado__eyebrow">Originación Individual · Paso 6</p>
          <h1>Resultado de Validación</h1>
          <p className="resultado__subtitle">
            Resultado del Análisis de Identidad
          </p>
          <p className="resultado__lede">
            El prospecto de cliente ha aprobado satisfactoriamente todos los
            filtros de validación de identidad e información del cumplimiento
            regulatorio interno.
          </p>
        </div>

        <aside
          className="resultado__panel"
          aria-label="Contexto de la radicación"
        >
          <dl className="resultado__meta">
            <div>
              <dt>Asesor</dt>
              <dd>Carlos Mendoza</dd>
            </div>
            <div>
              <dt>Sede</dt>
              <dd>Palmira - Centro Interno</dd>
            </div>
          </dl>
          <span className="resultado__server">
            <span aria-hidden="true" />
            Servidor de Validación Activo v2.4.12-Prod (SSL)
          </span>
        </aside>
      </header>

      <ol
        className="resultado__steps"
        aria-label="Etapas del proceso de originación"
      >
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
              className={`resultado__step ${estado}`}
              aria-current={posicion === PASO_ACTUAL ? 'step' : undefined}
            >
              <span className="resultado__step-number" aria-hidden="true">
                {posicion < PASO_ACTUAL ? '✓' : paso.number}
              </span>
              <span className="resultado__step-copy">
                <strong>{paso.label}</strong>
                <small>{paso.detail}</small>
              </span>
            </li>
          )
        })}
      </ol>

      <div className="resultado__hero" role="status">
        <span className="resultado__hero-icon" aria-hidden="true">
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
        </span>
        <div className="resultado__hero-copy">
          <strong>Solicitud aprobada en validación de identidad</strong>
          <span>
            Todos los criterios obligatorios fueron superados. Puedes radicar la
            solicitud de crédito.
          </span>
        </div>
        <span className="resultado__hero-badge">
          {criterios.length}/{criterios.length} criterios
        </span>
      </div>

      <div className="resultado__grid">
        <section className="resultado__card" aria-labelledby="criterios-title">
          <header className="resultado__card-head">
            <h2 id="criterios-title">Resumen de Criterios Obligatorios</h2>
            <span className="resultado__chip">Aprobado</span>
          </header>

          <ul className="resultado__criterios">
            {criterios.map((criterio) => (
              <li key={criterio.id} className="resultado__criterio">
                <span className="resultado__criterio-label">
                  {criterio.label}
                </span>
                <span
                  className={`resultado__criterio-estado is-${criterio.estado}`}
                >
                  <span
                    className="resultado__criterio-dot"
                    aria-hidden="true"
                  />
                  {criterio.valor}
                </span>
              </li>
            ))}
          </ul>
        </section>

        <section
          className="resultado__card resultado__card--seguimiento"
          aria-labelledby="seguimiento-title"
        >
          <header className="resultado__card-head">
            <h2 id="seguimiento-title">Requisitos de Seguimiento</h2>
            <span className="resultado__chip resultado__chip--warn">
              1 advertencia
            </span>
          </header>

          <div className="resultado__advertencia" role="note">
            <span className="resultado__advertencia-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" focusable="false">
                <circle
                  cx="12"
                  cy="12"
                  r="9"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                />
                <path
                  d="M12 7.5v5.5"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                />
                <circle cx="12" cy="16.4" r="1.1" fill="currentColor" />
              </svg>
            </span>
            <div className="resultado__advertencia-body">
              <strong>Comprobante Adicional</strong>
              <p>
                El cliente no tiene dirección física verificable en el
                documento. Se recomienda solicitar recibo de servicios públicos
                en la siguiente fase.
              </p>
            </div>
          </div>

          <p className="resultado__nota">
            *Esta es una advertencia operativa interna y no representa un
            rechazo automático de la solicitud de crédito del solicitante.
          </p>
        </section>
      </div>

      <section
        className="resultado__auditoria"
        aria-label="Trazabilidad de auditoría"
      >
        <div className="resultado__auditoria-head">
          <span className="resultado__auditoria-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" focusable="false">
              <path
                d="M12 3l8 4v6c0 4.2-2.8 7.2-8 8-5.2-.8-8-3.8-8-8V7l8-4Z"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinejoin="round"
              />
              <path
                d="M9 12l2 2 4-4.5"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </span>
          <h2>Trazabilidad de Auditoría Interna</h2>
        </div>

        <dl className="resultado__auditoria-grid">
          <div>
            <dt>Identificador de Validación</dt>
            <dd>
              <code>{identificador}</code>
            </dd>
          </div>
          <div>
            <dt>Nodo</dt>
            <dd>{nodo}</dd>
          </div>
          <div className="resultado__auditoria-full">
            <dt>Timestamp</dt>
            <dd>
              Confirmado con la Registraduría Nacional de Colombia y CIFIN.
            </dd>
          </div>
        </dl>
      </section>

      {creado && (
        <div
          className="resultado__banner resultado__banner--ok"
          role="status"
          aria-live="polite"
        >
          <strong>Solicitud de crédito creada.</strong>
          <span>
            Radicado <code>{identificador}</code>. Puedes continuar con la
            siguiente fase del proceso.
          </span>
        </div>
      )}

      <div className="resultado__actions">
        <div className="resultado__actions-left">
          {onBack && (
            <button
              className="resultado__back"
              type="button"
              onClick={onBack}
              disabled={enviando || creado}
            >
              ← Volver al paso anterior
            </button>
          )}
          <p className="resultado__actions-note">
            <span className="resultado__dot" aria-hidden="true" />
            {creado
              ? 'Solicitud radicada correctamente.'
              : 'Revisa los criterios antes de radicar.'}
          </p>
        </div>

        <button
          className="resultado__submit"
          type="button"
          onClick={handleCrearSolicitud}
          disabled={!aprobado || enviando || creado}
        >
          {enviando
            ? 'Creando solicitud…'
            : creado
              ? 'Solicitud creada'
              : 'Crear Solicitud de Crédito'}
        </button>
      </div>
    </div>
  )
}

export default ResultadoValidacion
