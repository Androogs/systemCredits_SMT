import { useState } from 'react'
import { ArrowLeft, ArrowRight } from 'lucide-react'
import Boton from '../../../shared/ui/Boton'
import SeguimientoOriginacion from './SeguimientoOriginacion/SeguimientoOriginacion'
import './PreparacionConsulta.css'

export interface DatosConsulta {
  nombreCompleto: string
  tipoDocumento: string
  numeroDocumento: string
  autorizacionFecha: string
  autorizacionIp: string
  iniciadaEn?: string
}

interface PreparacionConsultaProps {
  onContinue?: (datos: DatosConsulta) => void
  onBack?: () => void
  /** Si vienen del flujo real, se muestran los datos capturados. */
  inicial?: Partial<DatosConsulta>
}

const valoresIniciales: DatosConsulta = {
  nombreCompleto: 'CARLOS MARIO RESTREPO ALVAREZ',
  tipoDocumento: 'Cédula de Ciudadanía',
  numeroDocumento: '1.032.448.900',
  autorizacionFecha: '2026-03-04 15:34:10 COT',
  autorizacionIp: '186.154.43.12',
}

function PreparacionConsulta({
  onContinue,
  onBack,
  inicial,
}: PreparacionConsultaProps) {
  const [datos] = useState<DatosConsulta>({ ...valoresIniciales, ...inicial })
  const [enviando, setEnviando] = useState(false)
  const [iniciada, setIniciada] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleIniciar = () => {
    if (enviando || iniciada) return
    setError(null)
    setEnviando(true)

    // Simulación de inicio de consulta al buró. En producción reemplaza
    // por el POST al backend que dispara la petición a Datacrédito.
    window.setTimeout(() => {
      setEnviando(false)
      const iniciadaEn = new Date().toISOString()
      setIniciada(true)
      onContinue?.({ ...datos, iniciadaEn })
    }, 900)
  }

  return (
    <div className="consulta">
      <header className="consulta__header">
        <div className="consulta__header-copy">
          <p className="consulta__eyebrow">Originación Individual · Paso 8</p>
          <h1>Preparación de Consulta Crediticia</h1>
          <p className="consulta__subtitle">
            Preparación para Consulta a Central de Riesgos
          </p>
          <p className="consulta__lede">
            Asegure la trazabilidad de la consulta antes de lanzar la conexión
            con el buró crediticio nacional Datacrédito.
          </p>
        </div>

        <aside
          className="consulta__panel"
          aria-label="Contexto de la radicación"
        >
          <dl className="consulta__meta">
            <div>
              <dt>Asesor</dt>
              <dd>Carlos Mendoza</dd>
            </div>
            <div>
              <dt>Sede</dt>
              <dd>Palmira - Centro Interno</dd>
            </div>
          </dl>
          <span className="consulta__server">
            <span aria-hidden="true" />
            Servidor de Validación Activo v2.4.12-Prod (SSL)
          </span>
        </aside>
      </header>

      <SeguimientoOriginacion pasoActual={8} />

      <div className="consulta__grid">
        {/* ---------- Columna izquierda: identidad a consultar ---------- */}
        <section
          className="consulta__card"
          aria-labelledby="consulta-identidad"
        >
          <header className="consulta__card-head">
            <h2 id="consulta-identidad">Resumen de Consulta Regulada</h2>
            <span className="consulta__chip">Autorizado</span>
          </header>

          <div className="consulta__identidad">
            <span className="consulta__identidad-avatar" aria-hidden="true">
              {datos.nombreCompleto
                .split(' ')
                .slice(0, 2)
                .map((parte) => parte.charAt(0))
                .join('')}
            </span>
            <div className="consulta__identidad-copy">
              <span className="consulta__identidad-label">
                Identidad a Consultar
              </span>
              <strong>{datos.nombreCompleto}</strong>
              <span className="consulta__identidad-doc">
                <span aria-hidden="true">·</span> {datos.tipoDocumento} -{' '}
                {datos.numeroDocumento}
              </span>
            </div>
          </div>

          <dl className="consulta__detalle">
            <div>
              <dt>Documento de Identificación</dt>
              <dd>
                <span className="consulta__badge">CC</span>{' '}
                {datos.numeroDocumento}
              </dd>
            </div>
            <div>
              <dt>Buró a consultar</dt>
              <dd>Datacrédito (central nacional de riesgo)</dd>
            </div>
            <div>
              <dt>Tipo de consulta</dt>
              <dd>Verificación de crédito · Ley 1581 de 2012</dd>
            </div>
          </dl>
        </section>

        {/* ---------- Columna derecha: evidencia de consentimiento ---------- */}
        <section
          className="consulta__card consulta__card--consent"
          aria-labelledby="consulta-consent"
        >
          <header className="consulta__card-head">
            <h2 id="consulta-consent">
              Evidencia de Consentimiento Almacenado
            </h2>
            <span className="consulta__chip consulta__chip--ok">Firmada</span>
          </header>

          <p className="consulta__consent-text">
            Autorización expresa firmada el{' '}
            <strong>{datos.autorizacionFecha}</strong> desde el nodo IP{' '}
            <code>{datos.autorizacionIp}</code> por aceptación del cliente
            frente al asesor.
          </p>

          <ul className="consulta__consent-checks">
            <li>
              <span className="consulta__check" aria-hidden="true">
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
              Consentimiento informado (Habeas Data)
            </li>
            <li>
              <span className="consulta__check" aria-hidden="true">
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
              Identidad validada con Registraduría (98.4%)
            </li>
            <li>
              <span className="consulta__check" aria-hidden="true">
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
              Registro de auditoría con timestamp e IP del nodo
            </li>
          </ul>

          <p className="consulta__legal">
            * Este proceso se realiza en cumplimiento de la Ley de Habeas Data
            de Colombia, garantizando los derechos de acceso y rectificación del
            titular de los datos.
          </p>

          <div className="consulta__huella" role="note">
            <span className="consulta__huella-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" focusable="false">
                <path
                  d="M12 3c-3.3 0-6 2.7-6 6v4a2 2 0 0 0 2 2h1v-2a1 1 0 0 1 1-1h1v6"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d="M12 21c2.5 0 4.5-1.6 4.5-3.8V12c0-1.4-.5-2.7-1.5-3.6"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                />
                <path
                  d="M15.5 18c1.6-.7 2.5-2.1 2.5-4v-2"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                />
              </svg>
            </span>
            <p>
              La consulta generará una huella de auditoría interna visible para
              el buró.
            </p>
          </div>
        </section>
      </div>

      {iniciada && (
        <div
          className="consulta__banner consulta__banner--ok"
          role="status"
          aria-live="polite"
        >
          <strong>Consulta enviada al buró.</strong>
          <span>
            Datacrédito está procesando la solicitud. El resultado se mostrará
            en el Paso 9.
          </span>
        </div>
      )}

      {error && (
        <div className="consulta__banner consulta__banner--error" role="alert">
          <strong>No se pudo iniciar la consulta.</strong>
          <span>{error}</span>
        </div>
      )}

      <div className="consulta__actions">
        <div className="consulta__actions-left">
          {onBack && (
            <Boton
              variante="secundario"
              tamano="compacto"
              iconoInicio={<ArrowLeft size={14} aria-hidden="true" />}
              type="button"
              onClick={onBack}
              disabled={enviando || iniciada}
            >
              Modificar solicitud
            </Boton>
          )}
          <p className="consulta__actions-note">
            <span className="consulta__dot" aria-hidden="true" />
            {iniciada
              ? 'Consulta en curso · Paso 9 en progreso'
              : 'Revisa los datos antes de iniciar la consulta al buró.'}
          </p>
        </div>

        <Boton
          type="button"
          onClick={handleIniciar}
          disabled={enviando || iniciada}
          cargando={enviando}
          iconoFin={
            !enviando && !iniciada ? (
              <ArrowRight size={15} aria-hidden="true" />
            ) : undefined
          }
        >
          {enviando
            ? 'Iniciando consulta…'
            : iniciada
              ? 'Consulta en curso'
              : 'Iniciar Consulta Datacrédito'}
        </Boton>
      </div>
    </div>
  )
}

export default PreparacionConsulta
