import { useState } from 'react'
import { ArrowLeft, ArrowRight, ChevronDown, ChevronUp } from 'lucide-react'
import Boton from '../../../shared/ui/Boton'
import SeguimientoOriginacion from './SeguimientoOriginacion/SeguimientoOriginacion'
import { correoSchema, telefonoSchema } from '../schemas/persona'
import { contextoRadicacion } from '../../../shared/lib/sesion'
import { MODO_DEMO } from '../../../env'
import './AutorizacionDatos.css'

export interface DatosAutorizacion {
  autorizaTratamiento: boolean
  /** Celular del cliente: canal de notificaciones y OTP de firma. */
  telefono: string
  /** Correo del cliente: canal de notificaciones y OTP de firma. */
  correo: string
  fechaRegistro: string
  ipAsesor: string
}

interface AutorizacionDatosProps {
  onContinue?: (datos: DatosAutorizacion) => void
  onBack?: () => void
}

const IP_NO_CAPTURADA = 'no registrada'

/** Marca de tiempo de firma del consentimiento, en formato COT legible. */
function marcaTiempoActual(): string {
  const ahora = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${ahora.getFullYear()}-${pad(ahora.getMonth() + 1)}-${pad(ahora.getDate())} ${pad(ahora.getHours())}:${pad(ahora.getMinutes())}:${pad(ahora.getSeconds())} COT`
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
  const { asesor, sede } = contextoRadicacion()
  const [marcaRegistro] = useState(marcaTiempoActual)
  const [autoriza, setAutoriza] = useState(false)
  const [telefono, setTelefono] = useState('')
  const [correo, setCorreo] = useState('')
  const [intentado, setIntentado] = useState(false)
  const [registrado, setRegistrado] = useState(false)
  const [legalDesplegado, setLegalDesplegado] = useState(false)

  const error = intentado && !autoriza
  const errorTelefono = intentado
    ? (telefonoSchema.safeParse(telefono).error?.issues[0]?.message ?? null)
    : null
  const errorCorreo = intentado
    ? (correoSchema.safeParse(correo).error?.issues[0]?.message ?? null)
    : null

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setIntentado(true)

    if (
      !autoriza ||
      !telefonoSchema.safeParse(telefono).success ||
      !correoSchema.safeParse(correo).success
    ) {
      setRegistrado(false)
      return
    }

    setRegistrado(true)
    onContinue?.({
      autorizaTratamiento: true,
      telefono: telefono.trim(),
      correo: correo.trim(),
      fechaRegistro: marcaRegistro,
      // En dev se muestra una IP de ejemplo para completar la demo; en
      // producción queda como no capturada hasta que el backend registre
      // la IP real del asesor.
      ipAsesor: MODO_DEMO ? '186.154.43.12' : IP_NO_CAPTURADA,
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
        </div>

        <aside
          className="autorizacion__panel"
          aria-label="Contexto de la radicación"
        >
          <dl className="autorizacion__meta">
            <div>
              <dt>Asesor</dt>
              <dd>{asesor}</dd>
            </div>
            <div>
              <dt>Concesionario</dt>
              <dd>{sede}</dd>
            </div>
          </dl>
        </aside>
      </header>

      <SeguimientoOriginacion pasoActual={2} />

      <form className="autorizacion__form" onSubmit={handleSubmit} noValidate>
        <div className="autorizacion__form-head">
          <div>
            <h2>Resumen de Finalidad y Consentimiento Legal</h2>
            <p>
              El cliente debe leer y aceptar estas finalidades antes de
              continuar.
            </p>
          </div>
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
          <button
            type="button"
            className="autorizacion__legal-toggle"
            onClick={() => setLegalDesplegado(!legalDesplegado)}
            aria-expanded={legalDesplegado}
          >
            <span>Documentos Legales</span>
            {legalDesplegado ? (
              <ChevronUp size={20} aria-hidden="true" />
            ) : (
              <ChevronDown size={20} aria-hidden="true" />
            )}
          </button>

          {legalDesplegado && (
            <div className="autorizacion__legal-content">
              <ol className="autorizacion__legal-list">
                {finalidades.map((item) => (
                  <li key={item.number} className="autorizacion__legal-item">
                    <span
                      className="autorizacion__legal-number"
                      aria-hidden="true"
                    >
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
                href="/documentos/autorizacion-consulta-centrales-habeas-data.docx"
                download="Autorizacion consulta centrales - Habeas Data - Inversiones Pacifico.docx"
              >
                <svg
                  className="autorizacion__legal-icon"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                  focusable="false"
                >
                  <path
                    d="M12 3v12"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  <path
                    d="m7 10 5 5 5-5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  <path
                    d="M5 21h14"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                Descargar el documento legal completo de Habeas Data (DOCX)
              </a>
            </div>
          )}
        </div>

        <fieldset className="autorizacion__contacto">
          <legend>Datos de contacto del cliente</legend>
          <p className="autorizacion__contacto-nota">
            El cliente autoriza estos canales para recibir notificaciones del
            proceso (resultado, oferta y formalización) y el código de firma del
            pagaré.
          </p>
          <div className="autorizacion__contacto-grid">
            <div
              className={`autorizacion__contacto-field${
                errorTelefono ? ' has-error' : ''
              }`}
            >
              <label htmlFor="aut-telefono">
                Teléfono celular
                <span aria-hidden="true"> *</span>
              </label>
              <input
                id="aut-telefono"
                type="tel"
                inputMode="numeric"
                autoComplete="tel-national"
                maxLength={10}
                placeholder="Ej: 3001234567"
                value={telefono}
                aria-invalid={Boolean(errorTelefono)}
                onChange={(event) => {
                  setTelefono(event.target.value.replace(/\D/g, ''))
                  setRegistrado(false)
                }}
              />
              {errorTelefono && (
                <p className="autorizacion__error" role="alert">
                  {errorTelefono}
                </p>
              )}
            </div>
            <div
              className={`autorizacion__contacto-field${
                errorCorreo ? ' has-error' : ''
              }`}
            >
              <label htmlFor="aut-correo">
                Correo electrónico
                <span aria-hidden="true"> *</span>
              </label>
              <input
                id="aut-correo"
                type="email"
                autoComplete="email"
                placeholder="Ej: cliente@correo.com"
                value={correo}
                aria-invalid={Boolean(errorCorreo)}
                onChange={(event) => {
                  setCorreo(event.target.value)
                  setRegistrado(false)
                }}
              />
              {errorCorreo && (
                <p className="autorizacion__error" role="alert">
                  {errorCorreo}
                </p>
              )}
            </div>
          </div>
        </fieldset>

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

        <div className="autorizacion__actions">
          <div className="autorizacion__actions-left">
            {onBack && (
              <Boton
                variante="secundario"
                tamano="compacto"
                iconoInicio={<ArrowLeft size={14} aria-hidden="true" />}
                onClick={onBack}
              >
                Volver al paso anterior
              </Boton>
            )}
            <p className="autorizacion__actions-note">
              <span className="autorizacion__dot" aria-hidden="true" />
              Paso anterior guardado automáticamente
            </p>
          </div>
          <Boton
            type="submit"
            iconoFin={<ArrowRight size={15} aria-hidden="true" />}
          >
            Registrar y continuar
          </Boton>
        </div>
      </form>
    </div>
  )
}

export default AutorizacionDatos
