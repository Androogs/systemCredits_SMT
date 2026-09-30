import { useMemo, useState, type FormEvent } from 'react'
import './RevisionDatos.css'

export interface DatosRevisados {
  nombres: string
  apellidos: string
  numeroIdentificacion: string
  sexo: string
  fechaNacimiento: string
  lugarNacimiento: string
  fechaExpedicion: string
  ciudadExpedicion: string
}

interface RevisionDatosProps {
  onContinue?: (datos: DatosRevisados) => void
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

const PASO_ACTUAL = 5

const CONFIANZA_BASE = 98.4
const CONFIANZA_MAXIMA = 100

type CampoId =
  | 'nombres'
  | 'apellidos'
  | 'numeroIdentificacion'
  | 'sexo'
  | 'fechaNacimiento'
  | 'lugarNacimiento'
  | 'fechaExpedicion'
  | 'ciudadExpedicion'

interface DefinicionCampo {
  id: CampoId
  label: string
  tipo: 'text' | 'select' | 'date'
  opciones?: string[]
  /** El OCR marcó este campo como dudoso → requiere confirmación manual */
  dudoso?: boolean
  ayudaDudoso?: string
  soloLectura?: boolean
  placeholder?: string
}

const campos: DefinicionCampo[] = [
  { id: 'nombres', label: 'Nombres', tipo: 'text' },
  { id: 'apellidos', label: 'Apellidos', tipo: 'text' },
  {
    id: 'numeroIdentificacion',
    label: 'Número de Identificación (CC)',
    tipo: 'text',
    soloLectura: true,
  },
  {
    id: 'sexo',
    label: 'Sexo',
    tipo: 'select',
    opciones: ['Masculino (M)', 'Femenino (F)', 'No binario'],
  },
  { id: 'fechaNacimiento', label: 'Fecha de Nacimiento', tipo: 'date' },
  {
    id: 'lugarNacimiento',
    label: 'Lugar de Nacimiento',
    tipo: 'text',
    dudoso: true,
    ayudaDudoso: 'Campo dudoso. Confirmar con el físico de la cédula.',
  },
  {
    id: 'fechaExpedicion',
    label: 'Fecha de Expedición del Documento',
    tipo: 'date',
  },
  {
    id: 'ciudadExpedicion',
    label: 'Ciudad de Expedición',
    tipo: 'text',
    placeholder: 'Ej: Palmira, Valle del Cauca',
    dudoso: false,
  },
]

const valoresIniciales: DatosRevisados = {
  nombres: 'CARLOS MARIO',
  apellidos: 'RESTREPO ALVAREZ',
  numeroIdentificacion: '1.032.448.900',
  sexo: 'Masculino (M)',
  fechaNacimiento: '1991-08-15',
  lugarNacimiento: 'Medellín, Antioquia',
  fechaExpedicion: '2009-08-18',
  ciudadExpedicion: 'Palmira, Valle del Cauca',
}

function RevisionDatos({ onContinue, onBack }: RevisionDatosProps) {
  const [datos, setDatos] = useState<DatosRevisados>(valoresIniciales)
  const [dudososConfirmados, setDudososConfirmados] = useState<
    Record<string, boolean>
  >({})
  const [tocados, setTocados] = useState<Partial<Record<CampoId, boolean>>>({})
  const [intentado, setIntentado] = useState(false)
  const [registrado, setRegistrado] = useState(false)

  const errores = useMemo(() => {
    const lista: Partial<Record<CampoId, string>> = {}
    if (!datos.nombres.trim()) lista.nombres = 'Los nombres son obligatorios.'
    if (!datos.apellidos.trim())
      lista.apellidos = 'Los apellidos son obligatorios.'
    if (!datos.sexo) lista.sexo = 'Selecciona el sexo.'
    if (!datos.fechaNacimiento)
      lista.fechaNacimiento = 'Ingresa la fecha de nacimiento.'
    if (!datos.lugarNacimiento.trim())
      lista.lugarNacimiento = 'Confirma el lugar de nacimiento.'
    if (!datos.fechaExpedicion)
      lista.fechaExpedicion = 'Ingresa la fecha de expedición.'
    if (!datos.ciudadExpedicion.trim())
      lista.ciudadExpedicion = 'Confirma la ciudad de expedición.'
    return lista
  }, [datos])

  // ---------- Cálculo dinámico de confianza ----------
  const camposDudosos = useMemo(() => campos.filter((c) => c.dudoso), [])

  const dudososConfirmadosCount = camposDudosos.filter(
    (c) => dudososConfirmados[c.id],
  ).length

  const bonusPorConfirmacion =
    camposDudosos.length > 0
      ? (CONFIANZA_MAXIMA - CONFIANZA_BASE) / camposDudosos.length
      : 0

  const confianzaActual = Math.min(
    CONFIANZA_MAXIMA,
    CONFIANZA_BASE + dudososConfirmadosCount * bonusPorConfirmacion,
  )

  const confianzaCompleta = confianzaActual >= CONFIANZA_MAXIMA

  const nivelConfianza = confianzaCompleta
    ? 'VALIDADO'
    : confianzaActual >= 95
      ? 'ALTO'
      : confianzaActual >= 85
        ? 'MEDIO'
        : 'BAJO'

  const dudososPendientes = camposDudosos.filter(
    (c) => !dudososConfirmados[c.id],
  )

  const mostrarError = (campo: CampoId) =>
    Boolean(errores[campo]) && (intentado || tocados[campo])

  const marcarTocado = (campo: CampoId) =>
    setTocados((prev) => ({ ...prev, [campo]: true }))

  const actualizar = (campo: CampoId, valor: string) => {
    setDatos((prev) => ({ ...prev, [campo]: valor }))
    setRegistrado(false)
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setIntentado(true)

    if (Object.keys(errores).length > 0 || dudososPendientes.length > 0) {
      setRegistrado(false)
      return
    }

    setRegistrado(true)
    onContinue?.(datos)
  }

  return (
    <div className="revision">
      <header className="revision__header">
        <div className="revision__header-copy">
          <p className="revision__eyebrow">Originación Individual · Paso 5</p>
          <h1>Revisión de Datos Extraídos</h1>
          <p className="revision__subtitle">Confirmación de Datos OCR</p>
          <p className="revision__lede">
            Valida la precisión de los datos extraídos por el sistema. Los
            campos marcados en amarillo requieren confirmación manual debido a
            bajo nivel de confianza.
          </p>
        </div>

        <aside
          className="revision__panel"
          aria-label="Contexto de la radicación"
        >
          <dl className="revision__meta">
            <div>
              <dt>Asesor</dt>
              <dd>Carlos Mendoza</dd>
            </div>
            <div>
              <dt>Sede</dt>
              <dd>Palmira - Centro Interno</dd>
            </div>
          </dl>
          <span className="revision__server">
            <span aria-hidden="true" />
            Servidor de Validación Activo v2.4.12-Prod (SSL)
          </span>
        </aside>
      </header>

      <ol
        className="revision__steps"
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
              className={`revision__step ${estado}`}
              aria-current={posicion === PASO_ACTUAL ? 'step' : undefined}
            >
              <span className="revision__step-number" aria-hidden="true">
                {posicion < PASO_ACTUAL ? '✓' : paso.number}
              </span>
              <span className="revision__step-copy">
                <strong>{paso.label}</strong>
                <small>{paso.detail}</small>
              </span>
            </li>
          )
        })}
      </ol>

      <form className="revision__form" onSubmit={handleSubmit} noValidate>
        <div className="revision__form-head">
          <div>
            <h2>Datos Extraídos de Cédula</h2>
            <p>
              Los campos marcados con <span aria-hidden="true">*</span> son
              obligatorios.
            </p>
          </div>
          <span className="revision__chip">Paso 5 de 6</span>
        </div>

        <div className="revision__confianza" role="note">
          <div className="revision__confianza-copy">
            <span className="revision__confianza-label">
              Nivel de Confianza Global del Procesamiento
            </span>
            <small>
              Basado en legibilidad del documento anverso y reverso.
              {camposDudosos.length > 0 && (
                <>
                  {' '}
                  {dudososConfirmadosCount}/{camposDudosos.length} campo
                  {camposDudosos.length > 1 ? 's' : ''} dudoso
                  {camposDudosos.length > 1 ? 's' : ''} confirmado
                  {dudososConfirmadosCount === 1 ? '' : 's'} manualmente.
                </>
              )}
            </small>
          </div>

          <div className="revision__confianza-medidor">
            <span
              className={`revision__confianza-barra${
                confianzaCompleta ? ' is-completa' : ''
              }`}
              style={{ width: `${confianzaActual}%` }}
              aria-hidden="true"
            />
            <strong
              key={confianzaActual}
              className={`revision__confianza-valor${
                confianzaCompleta ? ' is-completa' : ''
              }`}
              aria-live="polite"
            >
              {confianzaActual.toFixed(1)}% · {nivelConfianza}
            </strong>
          </div>
        </div>

        {registrado && (
          <div className="revision__banner revision__banner--ok" role="status">
            <strong>Datos confirmados.</strong>
            <span>
              La información extraída fue validada por el asesor y queda lista
              para la radicación final.
            </span>
          </div>
        )}

        {intentado && dudososPendientes.length > 0 && (
          <div className="revision__banner revision__banner--warn" role="alert">
            <strong>Campos dudosos pendientes.</strong>
            <span>
              Confirma{' '}
              {dudososPendientes.length === 1
                ? 'el campo marcado'
                : 'los campos marcados'}{' '}
              en amarillo antes de continuar.
            </span>
          </div>
        )}

        <div className="revision__grid">
          {campos.map((campo) => {
            const error = mostrarError(campo.id)
            const dudosoPendiente =
              campo.dudoso && !dudososConfirmados[campo.id]
            const esSoloLectura = campo.soloLectura === true

            return (
              <div
                key={campo.id}
                className={`revision__field${error ? ' has-error' : ''}${
                  dudosoPendiente ? ' is-dudoso' : ''
                }${esSoloLectura ? ' is-readonly' : ''}`}
              >
                <label htmlFor={`rev-${campo.id}`}>
                  {campo.label}{' '}
                  <span className="revision__required" aria-hidden="true">
                    *
                  </span>
                  {dudosoPendiente && (
                    <span className="revision__badge-dudoso">
                      Requiere confirmación
                    </span>
                  )}
                </label>

                {campo.tipo === 'select' ? (
                  <div className="revision__input-wrap">
                    <select
                      id={`rev-${campo.id}`}
                      value={datos[campo.id]}
                      aria-invalid={error}
                      onChange={(event) =>
                        actualizar(campo.id, event.target.value)
                      }
                      onBlur={() => marcarTocado(campo.id)}
                    >
                      {campo.opciones?.map((opcion) => (
                        <option key={opcion} value={opcion}>
                          {opcion}
                        </option>
                      ))}
                    </select>
                    <span className="revision__select-arrow" aria-hidden="true">
                      ▾
                    </span>
                  </div>
                ) : (
                  <input
                    id={`rev-${campo.id}`}
                    type={campo.tipo === 'date' ? 'date' : 'text'}
                    value={datos[campo.id]}
                    readOnly={esSoloLectura}
                    aria-invalid={error}
                    placeholder={campo.placeholder}
                    onChange={(event) =>
                      actualizar(campo.id, event.target.value)
                    }
                    onBlur={() => marcarTocado(campo.id)}
                  />
                )}

                {campo.dudoso && (
                  <div className="revision__aviso-dudoso">
                    <span className="revision__aviso-icon" aria-hidden="true">
                      <svg viewBox="0 0 24 24" focusable="false">
                        <path
                          d="M12 3.5 21 19H3L12 3.5Z"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="1.8"
                          strokeLinejoin="round"
                        />
                        <path
                          d="M12 10v4"
                          stroke="currentColor"
                          strokeWidth="1.8"
                          strokeLinecap="round"
                        />
                        <circle cx="12" cy="16.6" r="1" fill="currentColor" />
                      </svg>
                    </span>
                    <div className="revision__aviso-body">
                      <p>{campo.ayudaDudoso}</p>
                      {dudosoPendiente ? (
                        <button
                          className="revision__confirmar"
                          type="button"
                          onClick={() =>
                            setDudososConfirmados((prev) => ({
                              ...prev,
                              [campo.id]: true,
                            }))
                          }
                        >
                          Confirmar campo
                        </button>
                      ) : (
                        <span className="revision__confirmado">
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
                          Confirmado por el asesor
                        </span>
                      )}
                    </div>
                  </div>
                )}

                {error && (
                  <p className="revision__error" role="alert">
                    {errores[campo.id]}
                  </p>
                )}
              </div>
            )
          })}
        </div>

        <div className="revision__actions">
          <div className="revision__actions-left">
            {onBack && (
              <button className="revision__back" type="button" onClick={onBack}>
                ← Volver al paso anterior
              </button>
            )}
            <p className="revision__actions-note">
              <span className="revision__dot" aria-hidden="true" />
              {dudososPendientes.length === 0
                ? 'Todos los campos dudosos fueron confirmados.'
                : `${dudososPendientes.length} campo(s) dudoso(s) por confirmar.`}
            </p>
          </div>
          <button className="revision__submit" type="submit">
            Confirmar y Continuar
          </button>
        </div>
      </form>
    </div>
  )
}

export default RevisionDatos
