import { useState } from 'react'
import './AutorizacionDatos.css'

export interface DatosAutorizacion {
  autorizaTratamiento: boolean
  fechaRegistro: string
  ipAsesor: string
}

interface AutorizacionDatosProps {
  onContinue?: (datos: DatosAutorizacion) => void
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

const PASO_ACTUAL = 2

const REGISTRO_AUDITORIA = {
  fecha: '2026-03-04 15:34:10 COT',
  ip: '186.154.43.12',
}

const finalidades = [
  {
    number: '1',
    title: 'FINALIDAD DEL TRATAMIENTO',
    body: 'Análisis de perfil de riesgo de crédito, estructuración del cupo financiero, prevención de lavado de activos (SARLAFT) y reportes de comportamiento de pago.',
  },
  {
    number: '2',
    title: 'CONSULTA Y ALMACENAMIENTO',
    body: 'Consultar e informar a centrales de riesgo autorizadas legalmente en el territorio nacional. Los datos se almacenarán por el tiempo estipulado en la ley colombiana.',
  },
] as const

function AutorizacionDatos({ onContinue, onBack }: AutorizacionDatosProps) {
  const [autoriza, setAutoriza] = useState(false)
  const [intentado, setIntentado] = useState(false)
  const [registrado, setRegistrado] = useState(false)

  const error = intentado && !autoriza

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setIntentado(true)

    if (!autoriza) {
      setRegistrado(false)
      return
    }

    setRegistrado(true)
    onContinue?.({
      autorizaTratamiento: true,
      fechaRegistro: REGISTRO_AUDITORIA.fecha,
      ipAsesor: REGISTRO_AUDITORIA.ip,
    })
  }

  return (
    <div className="autorizacion">
      <header className="autorizacion__header">
        <div className="autorizacion__header-copy">
          <p className="autorizacion__eyebrow">
            Originación Individual · Paso 2
          </p>
          <h1>Autorización Informada Habeas Data</h1>
          <p className="autorizacion__subtitle">
            Tratamiento de Datos Personales
          </p>
          <p className="autorizacion__lede">
            El cliente debe conocer y firmar formalmente el consentimiento
            informado para consulta en centrales de riesgo nacionales (CIFIN /
            Datacrédito).
          </p>
        </div>

        <aside
          className="autorizacion__panel"
          aria-label="Contexto de la radicación"
        >
          <dl className="autorizacion__meta">
            <div>
              <dt>Asesor</dt>
              <dd>Carlos Mendoza</dd>
            </div>
            <div>
              <dt>Sede</dt>
              <dd>Palmira - Centro Interno</dd>
            </div>
          </dl>
          <span className="autorizacion__server">
            <span aria-hidden="true" />
            Servidor de Validación Activo v2.4.12-Prod (SSL)
          </span>
        </aside>
      </header>

      <ol
        className="autorizacion__steps"
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
              className={`autorizacion__step ${estado}`}
              aria-current={posicion === PASO_ACTUAL ? 'step' : undefined}
            >
              <span className="autorizacion__step-number" aria-hidden="true">
                {posicion < PASO_ACTUAL ? '✓' : paso.number}
              </span>
              <span className="autorizacion__step-copy">
                <strong>{paso.label}</strong>
                <small>{paso.detail}</small>
              </span>
            </li>
          )
        })}
      </ol>

      <form className="autorizacion__form" onSubmit={handleSubmit} noValidate>
        <div className="autorizacion__form-head">
          <div>
            <h2>Resumen de Finalidad y Consentimiento Legal</h2>
            <p>
              El cliente debe leer y aceptar verbalmente las finalidades antes
              de continuar.
            </p>
          </div>
          <span className="autorizacion__chip">Paso 2 de 6</span>
        </div>

        {registrado && (
          <div
            className="autorizacion__banner autorizacion__banner--ok"
            role="status"
          >
            <strong>Autorización registrada.</strong>
            <span>
              El consentimiento informado quedó auditado con fecha, hora e IP
              del asesor.
            </span>
          </div>
        )}

        <div className="autorizacion__legal">
          <ol className="autorizacion__legal-list">
            {finalidades.map((item) => (
              <li key={item.number} className="autorizacion__legal-item">
                <span className="autorizacion__legal-number" aria-hidden="true">
                  {item.number}
                </span>
                <div className="autorizacion__legal-body">
                  <h3>{item.title}</h3>
                  <p>{item.body}</p>
                </div>
              </li>
            ))}
          </ol>

          <a
            className="autorizacion__legal-link"
            href="#habeas-data"
            target="_blank"
            rel="noopener noreferrer"
          >
            <svg
              className="autorizacion__legal-icon"
              viewBox="0 0 24 24"
              aria-hidden="true"
              focusable="false"
            >
              <path
                d="M14 4h6v6"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                d="M20 4 11 13"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                d="M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            Ver el documento legal completo de Habeas Data (PDF)
          </a>
        </div>

        <div
          className={`autorizacion__consent${error ? ' has-error' : ''}${
            autoriza ? ' is-checked' : ''
          }`}
        >
          <label className="autorizacion__consent-label">
            <input
              type="checkbox"
              checked={autoriza}
              aria-invalid={error}
              aria-describedby="consent-help"
              onChange={(event) => {
                setAutoriza(event.target.checked)
                setRegistrado(false)
              }}
            />
            <span className="autorizacion__consent-check" aria-hidden="true">
              <svg viewBox="0 0 24 24" focusable="false">
                <path
                  d="M5 12.5 10 17l9-10"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.4"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </span>
            <span className="autorizacion__consent-copy">
              <strong>
                El cliente autoriza el tratamiento de datos y consulta en
                centrales de riesgo.
              </strong>
              <small id="consent-help">
                No premarcada. Debe ser aceptada verbalmente y marcada por el
                asesor frente al cliente.
              </small>
            </span>
          </label>

          {error && (
            <p className="autorizacion__error" role="alert">
              Debes marcar la autorización del cliente para continuar.
            </p>
          )}
        </div>

        <div className="autorizacion__audit" role="note">
          <svg
            className="autorizacion__audit-icon"
            viewBox="0 0 24 24"
            aria-hidden="true"
            focusable="false"
          >
            <circle
              cx="12"
              cy="12"
              r="9"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
            />
            <path
              d="M12 7v5l3 2"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <p>
            <span>Registro Auditoría:</span> {REGISTRO_AUDITORIA.fecha} | IP del
            Nodo de Solicitud Asesor: {REGISTRO_AUDITORIA.ip}
          </p>
        </div>

        <div className="autorizacion__actions">
          <div className="autorizacion__actions-left">
            {onBack && (
              <button
                className="autorizacion__back"
                type="button"
                onClick={onBack}
              >
                ← Volver al paso anterior
              </button>
            )}
            <p className="autorizacion__actions-note">
              <span className="autorizacion__dot" aria-hidden="true" />
              Paso anterior guardado automáticamente
            </p>
          </div>
          <button className="autorizacion__submit" type="submit">
            Registrar y Continuar
          </button>
        </div>
      </form>
    </div>
  )
}

export default AutorizacionDatos
