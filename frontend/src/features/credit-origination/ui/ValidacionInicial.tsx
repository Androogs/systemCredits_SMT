import { useMemo, useState, type FormEvent } from 'react'
import { ArrowRight } from 'lucide-react'
import Boton from '../../../shared/ui/Boton'
import SeguimientoOriginacion from './SeguimientoOriginacion/SeguimientoOriginacion'
import { contextoRadicacion } from '../../../shared/lib/sesion'
import { MODO_DEMO } from '../../../env'
import {
  validacionInicialSchema,
  EDAD_MINIMA,
  EDAD_MAXIMA,
} from '../schemas/persona'
import './ValidacionInicial.css'

export interface DatosValidacion {
  tipoDocumento: string
  numeroDocumento: string
  /** ISO 'YYYY-MM-DD': la captura el asesor y el OCR la coteja. */
  fechaNacimiento: string
  nacionalidad: string
  multasPendientes: boolean
}

interface ValidacionInicialProps {
  onContinue?: (datos: DatosValidacion) => void
}

type Campo = 'numeroDocumento' | 'fechaNacimiento' | 'multas'

// Precarga de demostración: solo en dev (import.meta.env.DEV), nunca en
// el build de producción.
const DEMO = MODO_DEMO

const NACIONALIDADES = ['Colombiano(a)', 'Venezolano(a)', 'Otra'] as const
type Nacionalidad = (typeof NACIONALIDADES)[number]

interface DocumentoOpcion {
  codigo: string
  nombre: string
  /** Insignia corta junto al número de documento. */
  insignia: string
}

// El tipo de documento depende de la nacionalidad: a un colombiano se le
// exige CC; al extranjero, su cédula de extranjería (PPT/pasaporte aún no
// habilitados para crédito).
const DOCUMENTOS_POR_NACIONALIDAD: Record<Nacionalidad, DocumentoOpcion[]> = {
  'Colombiano(a)': [
    { codigo: 'CC', nombre: 'Cédula de Ciudadanía', insignia: 'CC COLOMBIANA' },
  ],
  'Venezolano(a)': [
    { codigo: 'CE', nombre: 'Cédula de Extranjería', insignia: 'CE' },
  ],
  Otra: [{ codigo: 'CE', nombre: 'Cédula de Extranjería', insignia: 'CE' }],
}

function ValidacionInicial({ onContinue }: ValidacionInicialProps) {
  const { asesor, sede } = contextoRadicacion()
  const [numeroDocumento, setNumeroDocumento] = useState(
    DEMO ? '1032448900' : '',
  )
  const [fechaNacimiento, setFechaNacimiento] = useState(
    DEMO ? '1991-08-15' : '',
  )
  const [multas, setMultas] = useState<'si' | 'no' | ''>(DEMO ? 'no' : '')
  const [nacionalidad, setNacionalidad] = useState<Nacionalidad>(
    NACIONALIDADES[0],
  )
  const documentos = DOCUMENTOS_POR_NACIONALIDAD[nacionalidad]
  const [tipoDocumento, setTipoDocumento] = useState(documentos[0].codigo)
  const insignia =
    documentos.find((d) => d.codigo === tipoDocumento)?.insignia ??
    tipoDocumento
  const [tocados, setTocados] = useState<Partial<Record<Campo, boolean>>>({})
  const [intentado, setIntentado] = useState(false)
  const [resultado, setResultado] = useState<'idle' | 'ok' | 'error'>('idle')

  const errores = useMemo(() => {
    const resultado = validacionInicialSchema.safeParse({
      numeroDocumento,
      fechaNacimiento,
      multas: multas === '' ? undefined : multas,
    })
    if (resultado.success) return {}
    const lista: Partial<Record<Campo, string>> = {}
    for (const issue of resultado.error.issues) {
      const campo = issue.path[0] as Campo
      if (campo && !(campo in lista)) lista[campo] = issue.message
    }
    return lista
  }, [numeroDocumento, fechaNacimiento, multas])

  const mostrarError = (campo: Campo) =>
    Boolean(errores[campo]) && (intentado || tocados[campo])

  const marcarTocado = (campo: Campo) =>
    setTocados((previo) => ({ ...previo, [campo]: true }))

  const limpiarResultado = () => setResultado('idle')

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setIntentado(true)

    if (Object.keys(errores).length > 0) {
      setResultado('error')
      return
    }

    setResultado('ok')
    onContinue?.({
      tipoDocumento,
      numeroDocumento,
      fechaNacimiento,
      nacionalidad,
      multasPendientes: multas === 'si',
    })
  }

  return (
    <div className="validacion">
      <header className="validacion__header">
        <div className="validacion__header-copy">
          <p className="validacion__eyebrow">Originación Individual · Paso 1</p>
          <h1>Validación Inicial</h1>
          <p className="validacion__subtitle">
            Datos y filtros básicos del cliente
          </p>
        </div>

        <aside
          className="validacion__panel"
          aria-label="Contexto de la radicación"
        >
          <dl className="validacion__meta">
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

      <SeguimientoOriginacion pasoActual={1} />

      <form className="validacion__form" onSubmit={handleSubmit} noValidate>
        <div className="validacion__form-head">
          <div>
            <h2>Verificación de Políticas Clave</h2>
            <p>
              Los campos marcados con <span aria-hidden="true">*</span> son
              obligatorios.
            </p>
          </div>
        </div>

        {resultado === 'ok' && (
          <div
            className="validacion__banner validacion__banner--ok"
            role="status"
          >
            <strong>Validación inicial superada.</strong>
            <span>
              Los datos cumplen los criterios mínimos. Puedes continuar con el
              tratamiento de datos.
            </span>
          </div>
        )}

        {resultado === 'error' && (
          <div
            className="validacion__banner validacion__banner--error"
            role="alert"
          >
            <strong>Revisa los campos marcados.</strong>
            <span>Aún hay datos obligatorios pendientes por corregir.</span>
          </div>
        )}

        <div className="validacion__grid">
          <div className="validacion__field">
            <label htmlFor="tipo-documento">
              Tipo de Documento{' '}
              <span className="validacion__required" aria-hidden="true">
                *
              </span>
            </label>
            <select
              id="tipo-documento"
              value={tipoDocumento}
              onChange={(event) => {
                setTipoDocumento(event.target.value)
                limpiarResultado()
              }}
            >
              {documentos.map((doc) => (
                <option key={doc.codigo} value={doc.codigo}>
                  {doc.nombre}
                </option>
              ))}
            </select>
            {documentos.length === 1 && (
              <p className="validacion__hint">
                Único documento aceptado para esta nacionalidad.
              </p>
            )}
          </div>

          <div
            className={`validacion__field${mostrarError('numeroDocumento') ? ' has-error' : ''}`}
          >
            <label htmlFor="numero-documento">
              Número de Cédula{' '}
              <span className="validacion__required" aria-hidden="true">
                *
              </span>
            </label>
            <div className="validacion__input-group">
              <input
                id="numero-documento"
                type="text"
                inputMode="numeric"
                autoComplete="off"
                value={numeroDocumento}
                aria-invalid={mostrarError('numeroDocumento')}
                onChange={(event) => {
                  setNumeroDocumento(
                    event.target.value.replace(/\D/g, '').slice(0, 10),
                  )
                  limpiarResultado()
                }}
                onBlur={() => marcarTocado('numeroDocumento')}
              />
              <span className="validacion__badge">{insignia}</span>
            </div>
            {mostrarError('numeroDocumento') ? (
              <p className="validacion__error" role="alert">
                {errores.numeroDocumento}
              </p>
            ) : null}
          </div>

          <div
            className={`validacion__field${mostrarError('fechaNacimiento') ? ' has-error' : ''}`}
          >
            <label htmlFor="fecha-nacimiento">
              Fecha de Nacimiento{' '}
              <span className="validacion__required" aria-hidden="true">
                *
              </span>
            </label>
            <div className="validacion__input-group validacion__input-group--fecha">
              <input
                id="fecha-nacimiento"
                type="date"
                value={fechaNacimiento}
                max={new Date().toISOString().slice(0, 10)}
                aria-invalid={mostrarError('fechaNacimiento')}
                onChange={(event) => {
                  setFechaNacimiento(event.target.value)
                  limpiarResultado()
                }}
                onBlur={() => marcarTocado('fechaNacimiento')}
              />
            </div>
            {mostrarError('fechaNacimiento') ? (
              <p className="validacion__error" role="alert">
                {errores.fechaNacimiento}
              </p>
            ) : (
              <p className="validacion__hint">
                Debe tener entre {EDAD_MINIMA} y {EDAD_MAXIMA} años para
                radicación de crédito. El OCR de la cédula coteja esta fecha.
              </p>
            )}
          </div>

          <div className="validacion__field">
            <label htmlFor="nacionalidad">
              Nacionalidad{' '}
              <span className="validacion__required" aria-hidden="true">
                *
              </span>
            </label>
            <select
              id="nacionalidad"
              value={nacionalidad}
              onChange={(event) => {
                const nueva = event.target.value as Nacionalidad
                setNacionalidad(nueva)
                setTipoDocumento(DOCUMENTOS_POR_NACIONALIDAD[nueva][0].codigo)
                limpiarResultado()
              }}
            >
              {NACIONALIDADES.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </div>

          <div
            className={`validacion__field validacion__field--full${
              mostrarError('multas') ? ' has-error' : ''
            }`}
          >
            <span className="validacion__label" id="multas-label">
              ¿Tiene multas pendientes de pago?{' '}
              <span className="validacion__required" aria-hidden="true">
                *
              </span>
            </span>

            <div
              className="validacion__toggle"
              role="radiogroup"
              aria-labelledby="multas-label"
            >
              <button
                type="button"
                role="radio"
                aria-checked={multas === 'si'}
                className={`validacion__toggle-option${multas === 'si' ? ' is-active' : ''}`}
                onClick={() => {
                  setMultas('si')
                  marcarTocado('multas')
                  limpiarResultado()
                }}
              >
                Sí
              </button>

              <button
                type="button"
                role="radio"
                aria-checked={multas === 'no'}
                className={`validacion__toggle-option${multas === 'no' ? ' is-active' : ''}`}
                onClick={() => {
                  setMultas('no')
                  marcarTocado('multas')
                  limpiarResultado()
                }}
              >
                No
              </button>
            </div>

            {mostrarError('multas') ? (
              <p className="validacion__error" role="alert">
                {errores.multas}
              </p>
            ) : multas === 'si' ? (
              <p className="validacion__warning" role="status">
                El solicitante registra sanciones pendientes: la radicación
                puede quedar en revisión manual.
              </p>
            ) : null}
          </div>
        </div>

        <div className="validacion__actions">
          <p className="validacion__actions-note">
            Al continuar, el sistema registra la validación inicial y habilita
            el paso de tratamiento de datos.
          </p>
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

export default ValidacionInicial
