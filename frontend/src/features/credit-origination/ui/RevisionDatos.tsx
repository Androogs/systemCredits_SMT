import { useMemo, useState, type FormEvent } from 'react'
import { ArrowLeft, ArrowRight } from 'lucide-react'
import Boton from '../../../shared/ui/Boton'
import { emitirToast } from '../../../shared/lib/toastBus'
import SeguimientoOriginacion from './SeguimientoOriginacion/SeguimientoOriginacion'
import { contextoRadicacion } from '../../../shared/lib/sesion'
import { datosPersonalesSchema } from '../schemas/persona'
import type { CampoOCRApi, ResultadoOCRApi } from '../api/originacionApi'
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
  /** Resultado del OCR de la cédula; si trae advertencias, se muestran aquí. */
  ocr?: ResultadoOCRApi | null
}

/** Por debajo de esta confianza del OCR, el campo pide confirmación manual. */
const CONFIANZA_DUDOSA = 75

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

/** Campo del formulario → campo del OCR (para su confianza). */
const CAMPO_OCR: Record<CampoId, keyof ResultadoOCRApi> = {
  nombres: 'nombres',
  apellidos: 'apellidos',
  numeroIdentificacion: 'numero_documento',
  sexo: 'sexo',
  fechaNacimiento: 'fecha_nacimiento',
  lugarNacimiento: 'lugar_nacimiento',
  fechaExpedicion: 'fecha_expedicion',
  ciudadExpedicion: 'ciudad_expedicion',
}

const camposBase: DefinicionCampo[] = [
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
  },
]

function campoOCR(
  ocr: ResultadoOCRApi | null | undefined,
  id: CampoId,
): CampoOCRApi | undefined {
  const valor = ocr?.[CAMPO_OCR[id]]
  return valor && typeof valor === 'object' && 'confianza' in valor
    ? (valor as CampoOCRApi)
    : undefined
}

/** Palabras de la advertencia OCR que delatan a cada campo (datos que
 * no coinciden entre lo capturado, el anverso y el reverso). */
const ADVERTENCIA_POR_CAMPO: Partial<Record<CampoId, RegExp>> = {
  numeroIdentificacion: /documento|número/i,
  nombres: /nombres?/i,
  apellidos: /apellidos?/i,
  fechaNacimiento: /fecha de nacimiento/i,
}

/**
 * Marca como dudoso un campo solo con evidencia real de discrepancia:
 * el OCR lo leyó con baja confianza o una advertencia lo nombra (el
 * dato leído no coincide con lo capturado o entre caras). Un campo que
 * el OCR no leyó no se marca: el asesor lo digita y la validación del
 * formulario exige el valor.
 */
function construirCampos(
  ocr: ResultadoOCRApi | null | undefined,
): DefinicionCampo[] {
  const advertencias = ocr?.advertencias ?? []
  return camposBase.map((campo) => {
    if (campo.soloLectura || !ocr?.disponible) return campo
    const advertencia = ADVERTENCIA_POR_CAMPO[campo.id]
      ? advertencias.find((a) => ADVERTENCIA_POR_CAMPO[campo.id]!.test(a))
      : undefined
    if (advertencia) {
      return { ...campo, dudoso: true, ayudaDudoso: advertencia }
    }
    const leido = campoOCR(ocr, campo.id)
    if (
      leido?.valor &&
      leido.confianza > 0 &&
      leido.confianza < CONFIANZA_DUDOSA
    ) {
      return {
        ...campo,
        dudoso: true,
        ayudaDudoso: `El OCR leyó este dato con baja confianza (${Math.round(
          leido.confianza,
        )} %). Confírmalo con el físico de la cédula.`,
      }
    }
    return campo
  })
}

// Precarga vacía: los valores llegan por `inicial` (paso 1) y por `ocr`
// (cédula escaneada). Nada de datos quemados: enmascaraban fallos del OCR.
const valoresIniciales: DatosRevisados = {
  nombres: '',
  apellidos: '',
  numeroIdentificacion: '',
  sexo: '',
  fechaNacimiento: '',
  lugarNacimiento: '',
  fechaExpedicion: '',
  ciudadExpedicion: '',
}

/** Normaliza el sexo del OCR al vocabulario del select. */
function normalizarSexo(valor: string): string {
  const plano = valor.trim().toUpperCase()
  if (!plano) return ''
  if (plano.startsWith('F')) return 'Femenino (F)'
  if (plano.startsWith('M')) return 'Masculino (M)'
  return valor
}

/** Traduce el ResultadoOCRApi (snake_case) a los campos del formulario. */
function mapearOCR(
  ocr: ResultadoOCRApi | null | undefined,
): Partial<DatosRevisados> {
  if (!ocr) return {}
  const salida: Partial<DatosRevisados> = {}
  const doc = ocr.numero_documento?.valor?.replace(/\D/g, '') ?? ''
  if (doc) salida.numeroIdentificacion = doc
  if (ocr.nombres?.valor) salida.nombres = ocr.nombres.valor
  if (ocr.apellidos?.valor) salida.apellidos = ocr.apellidos.valor
  if (ocr.fecha_nacimiento?.valor)
    salida.fechaNacimiento = ocr.fecha_nacimiento.valor
  if (ocr.fecha_expedicion?.valor)
    salida.fechaExpedicion = ocr.fecha_expedicion.valor
  const sexo = normalizarSexo(ocr.sexo?.valor ?? '')
  if (sexo) salida.sexo = sexo
  if (ocr.lugar_nacimiento?.valor)
    salida.lugarNacimiento = ocr.lugar_nacimiento.valor
  if (ocr.ciudad_expedicion?.valor)
    salida.ciudadExpedicion = ocr.ciudad_expedicion.valor
  return salida
}

const ETIQUETA_TIPO: Record<string, string> = {
  blanca: 'Cédula digital (blanca)',
  amarilla: 'Cédula amarilla con hologramas',
}

function RevisionDatos({
  onContinue,
  onBack,
  inicial,
  compacto = false,
  ocr = null,
}: RevisionDatosProps) {
  const { asesor, sede } = contextoRadicacion()
  const [datos, setDatos] = useState<DatosRevisados>(() => ({
    ...valoresIniciales,
    ...mapearOCR(ocr),
    ...Object.fromEntries(
      Object.entries(inicial ?? {}).filter(
        ([, v]) => v !== undefined && v !== '',
      ),
    ),
  }))
  const [dudososConfirmados, setDudososConfirmados] = useState<
    Record<string, boolean>
  >({})
  const [tocados, setTocados] = useState<Partial<Record<CampoId, boolean>>>({})
  const [intentado, setIntentado] = useState(false)
  const [registrado, setRegistrado] = useState(false)

  const campos = useMemo(() => construirCampos(ocr), [ocr])

  // Advertencias del OCR: la cédula leída no concuerda con lo capturado en el
  // paso 1 o el anverso no concuerda con el reverso. No bloquea — el asesor
  // decide si corrige o continúa.
  const advertenciasOCR = ocr?.advertencias ?? []
  const observacionesOCR = ocr?.observaciones ?? []
  const [advertenciasVistas, setAdvertenciasVistas] = useState(false)
  const tipoCedula = ocr?.tipo_cedula ? ETIQUETA_TIPO[ocr.tipo_cedula] : null

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

  const camposDudosos = useMemo(() => campos.filter((c) => c.dudoso), [campos])

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
              campos marcados en amarillo requieren confirmación: el OCR los
              leyó con baja confianza o no coinciden con lo capturado.
            </p>
          </div>

          <aside
            className="revision__panel"
            aria-label="Contexto de la radicación"
          >
            <dl className="revision__meta">
              <div>
                <dt>Asesor</dt>
                <dd>{asesor}</dd>
              </div>
              <div>
                <dt>Sede</dt>
                <dd>{sede}</dd>
              </div>
            </dl>
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
              {tipoCedula && (
                <>
                  Documento detectado: <strong>{tipoCedula}</strong>.{' '}
                </>
              )}
              Los campos marcados con <span aria-hidden="true">*</span> son
              obligatorios.
            </p>
          </div>
        </div>

        {advertenciasOCR.length > 0 && !advertenciasVistas && (
          <div className="revision__banner revision__banner--warn" role="alert">
            <span className="revision__banner-icon" aria-hidden="true">
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
            <div className="revision__banner-body">
              <strong>Los datos no coinciden.</strong>
              <span className="revision__banner-sub">
                Verifica con la cédula física antes de continuar.
              </span>
              <ul className="revision__ocr-lista">
                {advertenciasOCR.map((aviso) => (
                  <li key={aviso}>{aviso}</li>
                ))}
              </ul>
            </div>
            <Boton
              variante="terciario"
              tamano="compacto"
              type="button"
              className="revision__banner-action"
              onClick={() => setAdvertenciasVistas(true)}
            >
              Entendido
            </Boton>
          </div>
        )}

        {observacionesOCR.length > 0 && (
          <div className="revision__banner revision__banner--warn" role="note">
            <span className="revision__banner-icon" aria-hidden="true">
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
                  d="M12 8v4"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                />
                <circle cx="12" cy="15.6" r="1" fill="currentColor" />
              </svg>
            </span>
            <div className="revision__banner-body">
              <strong>Revisa la captura.</strong>
              <ul className="revision__ocr-lista">
                {observacionesOCR.map((nota) => (
                  <li key={nota}>{nota}</li>
                ))}
              </ul>
            </div>
          </div>
        )}

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
                    type={campo.tipo}
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
