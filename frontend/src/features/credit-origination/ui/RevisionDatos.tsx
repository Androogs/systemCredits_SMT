import { useMemo, useState, type FormEvent } from 'react'
import { ArrowLeft, ArrowRight } from 'lucide-react'
import Boton from '../../../shared/ui/Boton'
import { emitirToast } from '../../../shared/lib/toastBus'
import SeguimientoOriginacion from './SeguimientoOriginacion/SeguimientoOriginacion'
import { datosPersonalesSchema } from '../schemas/persona'
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
  /** Valores extraídos por el OCR / digitados en el paso 1. */
  inicial?: Partial<DatosRevisados>
  /** Si es true, no renderiza header ni seguimiento (para usar dentro de otro paso). */
  compacto?: boolean
}

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
    label: 'N° de Identificación',
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
    label: 'Fecha de Expedición',
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

// Precarga de demostración solo en dev (import.meta.env.DEV); en el
// build de producción todos los campos arrancan vacíos.
const valoresIniciales: DatosRevisados = import.meta.env.DEV
  ? {
      nombres: 'CARLOS MARIO',
      apellidos: 'RESTREPO ALVAREZ',
      numeroIdentificacion: '',
      sexo: 'Masculino (M)',
      fechaNacimiento: '1991-03-14',
      lugarNacimiento: 'Palmira, Valle del Cauca',
      fechaExpedicion: '2010-04-20',
      ciudadExpedicion: 'Palmira, Valle del Cauca',
    }
  : {
      nombres: '',
      apellidos: '',
      numeroIdentificacion: '',
      sexo: '',
      fechaNacimiento: '',
      lugarNacimiento: '',
      fechaExpedicion: '',
      ciudadExpedicion: '',
    }

function RevisionDatos({
  onContinue,
  onBack,
  inicial,
  compacto = false,
}: RevisionDatosProps) {
  const [datos, setDatos] = useState<DatosRevisados>(() => ({
    ...valoresIniciales,
    ...Object.fromEntries(
      Object.entries(inicial ?? {}).filter(([, v]) => v !== undefined),
    ),
  }))
  const [dudososConfirmados, setDudososConfirmados] = useState<
    Record<string, boolean>
  >({})
  const [tocados, setTocados] = useState<Partial<Record<CampoId, boolean>>>({})
  const [intentado, setIntentado] = useState(false)
  const [registrado, setRegistrado] = useState(false)

  const errores = useMemo(() => {
    const resultado = datosPersonalesSchema.safeParse(datos)
    if (resultado.success) return {}
    const lista: Partial<Record<CampoId, string>> = {}
    for (const issue of resultado.error.issues) {
      const campo = issue.path[0] as CampoId
      if (campo && !(campo in lista)) lista[campo] = issue.message
    }
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

  const confirmarDudoso = (campo: DefinicionCampo) => {
    setDudososConfirmados((prev) => ({ ...prev, [campo.id]: true }))
    emitirToast({
      tipo: 'exito',
      titulo: 'Campo confirmado',
      mensaje: `${campo.label} fue validado por el asesor.`,
    })
  }

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
      {!compacto && (
        <header className="revision__header">
          <div className="revision__header-copy">
            <p className="revision__eyebrow">Originación Individual · Paso 3</p>
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
      )}

      {!compacto && <SeguimientoOriginacion pasoActual={3} />}

      <form
        className={`revision__form${compacto ? ' revision__form--compacto' : ''}`}
        onSubmit={handleSubmit}
        noValidate
      >
        <div className="revision__form-head">
          <div>
            <h2>Datos extraídos de la cédula</h2>
            <p>
              Los campos marcados con <span aria-hidden="true">*</span> son
              obligatorios.
            </p>
          </div>
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

          <div className="revision__confianza-metrica">
            <div className="revision__confianza-medidor">
              <span
                className={`revision__confianza-barra${
                  confianzaCompleta ? ' is-completa' : ''
                }`}
                style={{ width: `${confianzaActual}%` }}
                aria-hidden="true"
              />
            </div>
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
                }${dudosoPendiente ? ' has-aviso' : ''}${
                  esSoloLectura ? ' is-readonly' : ''
                }`}
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
                      <option value="" disabled>
                        Selecciona una opción…
                      </option>
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

                {campo.dudoso && dudosoPendiente && (
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
                      <Boton
                        variante="terciario"
                        tamano="compacto"
                        type="button"
                        onClick={() => confirmarDudoso(campo)}
                      >
                        Confirmar campo
                      </Boton>
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
              <Boton
                variante="secundario"
                tamano="compacto"
                iconoInicio={<ArrowLeft size={14} aria-hidden="true" />}
                onClick={onBack}
              >
                Volver al paso anterior
              </Boton>
            )}
            <p className="revision__actions-note">
              <span className="revision__dot" aria-hidden="true" />
              {dudososPendientes.length === 0
                ? 'Todos los campos dudosos fueron confirmados.'
                : `${dudososPendientes.length} campo(s) dudoso(s) por confirmar.`}
            </p>
          </div>
          <Boton
            type="submit"
            iconoFin={<ArrowRight size={15} aria-hidden="true" />}
          >
            Confirmar y Continuar
          </Boton>
        </div>
      </form>
    </div>
  )
}

export default RevisionDatos
