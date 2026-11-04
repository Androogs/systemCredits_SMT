import { useMemo, useState, type FormEvent } from 'react'
import { ArrowLeft, ArrowRight } from 'lucide-react'
import Boton from '../../../shared/ui/Boton'
import { emitirToast } from '../../../shared/lib/toastBus'
import SeguimientoOriginacion from './SeguimientoOriginacion/SeguimientoOriginacion'
import { contextoRadicacion } from '../../../shared/lib/sesion'
import { datosPersonalesSchema } from '../schemas/persona'
import type { CampoOCRApi, ResultadoOCRApi } from '../api/originacionApi'
import {
  DOCUMENTOS_POR_NACIONALIDAD,
  NACIONALIDAD_API,
  NACIONALIDADES,
  nacionalidadDesdeApi,
  type DatosValidacion,
  type Nacionalidad,
} from '../model/politicas-clave'
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
  /** Entrega los datos de la cédula y la verificación de políticas clave. */
  onContinue?: (datos: DatosRevisados, validacion: DatosValidacion) => void
  onBack?: () => void
  /** Valores previos (retomar o volver desde el paso siguiente). */
  inicial?: Partial<DatosRevisados>
  /** Políticas ya capturadas; `nacionalidad` en su forma canónica (API). */
  inicialPoliticas?: Partial<
    Pick<DatosValidacion, 'nacionalidad' | 'tipoDocumento' | 'multasPendientes'>
  >
  /** Si es true, no renderiza header ni seguimiento (para usar dentro de otro paso). */
  compacto?: boolean
  /** Resultado del OCR de la cédula; si trae advertencias, se muestran aquí. */
  ocr?: ResultadoOCRApi | null
}

const CONFIANZA_MAXIMA = 100
/** Por debajo de esta confianza del OCR, el campo pide confirmación manual. */
const CONFIANZA_DUDOSA = 75

type CampoPolitica = 'nacionalidad' | 'tipoDocumento' | 'multas' | 'simit'

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
  {
    id: 'nombres',
    label: 'Nombres',
    tipo: 'text',
    placeholder: 'Ej: Ana María',
  },
  {
    id: 'apellidos',
    label: 'Apellidos',
    tipo: 'text',
    placeholder: 'Ej: Pérez Gómez',
  },
  {
    id: 'numeroIdentificacion',
    label: 'N° de Identificación',
    tipo: 'text',
    placeholder: 'Ej: 1023456789',
  },
  {
    id: 'sexo',
    label: 'Género',
    tipo: 'select',
    opciones: [
      'Masculino (M)',
      'Femenino (F)',
      'No binario (NB)',
      'Transexual (T)',
    ],
  },
  { id: 'fechaNacimiento', label: 'Fecha de Nacimiento', tipo: 'date' },
  {
    id: 'lugarNacimiento',
    label: 'Lugar de Nacimiento',
    tipo: 'text',
    placeholder: 'Ej: Cali, Valle del Cauca',
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
  sexo: /sexo|género/i,
  fechaNacimiento: /fecha de nacimiento/i,
  lugarNacimiento: /lugar de nacimiento/i,
  fechaExpedicion: /fecha de expedición/i,
  ciudadExpedicion: /ciudad de expedición/i,
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

// Precarga vacía: los valores llegan por `inicial` (ya confirmados) y por `ocr`
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

// Texto libre siempre en mayúsculas: lo digitado y lo precargado por OCR.
const CAMPOS_MAYUSCULAS: CampoId[] = [
  'nombres',
  'apellidos',
  'lugarNacimiento',
  'ciudadExpedicion',
]

function enMayusculas(datos: DatosRevisados): DatosRevisados {
  const salida = { ...datos }
  for (const id of CAMPOS_MAYUSCULAS) salida[id] = salida[id].toUpperCase()
  return salida
}

/** Normaliza el sexo del OCR al vocabulario del select. */
function normalizarSexo(valor: string): string {
  const plano = valor.trim().toUpperCase()
  if (!plano) return ''
  if (plano === 'NB' || plano === 'X' || plano.startsWith('NO B'))
    return 'No binario (NB)'
  if (plano.startsWith('T')) return 'Transexual (T)'
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

/**
 * Nacionalidad y tipo de documento deducidos del diseño de cédula leído:
 * blanca/amarilla son la CC colombiana; el PPT es de venezolanos, pero no
 * es un documento aceptado, así que el tipo queda para el asesor.
 */
function politicasDesdeOCR(ocr: ResultadoOCRApi | null | undefined): {
  nacionalidad: Nacionalidad | ''
  tipoDocumento: string
} {
  switch (ocr?.tipo_cedula) {
    case 'blanca':
    case 'amarilla':
      return { nacionalidad: 'Colombiano(a)', tipoDocumento: 'CC' }
    case 'ppt':
      return { nacionalidad: 'Venezolano(a)', tipoDocumento: '' }
    default:
      return { nacionalidad: '', tipoDocumento: '' }
  }
}

// SIMIT no permite mostrarse embebido (X-Frame-Options: SAMEORIGIN): se
// abre en una ventana emergente centrada sobre la app.
const URL_SIMIT = 'https://www.fcm.org.co/simit/#/home-public'

function abrirSimit() {
  const ancho = Math.min(1100, window.screen.availWidth - 80)
  const alto = Math.min(800, window.screen.availHeight - 80)
  const izquierda = Math.round(window.screenX + (window.outerWidth - ancho) / 2)
  const arriba = Math.round(window.screenY + (window.outerHeight - alto) / 2)
  const ventana = window.open(
    URL_SIMIT,
    'consulta-simit',
    `popup,width=${ancho},height=${alto},left=${izquierda},top=${arriba}`,
  )
  if (ventana) {
    ventana.focus()
  } else {
    emitirToast({
      tipo: 'error',
      titulo: 'No se pudo abrir el SIMIT',
      mensaje:
        'El navegador bloqueó la ventana emergente. Permite ventanas emergentes para este sitio.',
    })
  }
}

const ETIQUETA_TIPO: Record<string, string> = {
  blanca: 'Cédula digital (blanca)',
  amarilla: 'Cédula amarilla con hologramas',
  ppt: 'Permiso por Protección Temporal (documento no aceptado)',
}

function RevisionDatos({
  onContinue,
  onBack,
  inicial,
  inicialPoliticas,
  compacto = false,
  ocr = null,
}: RevisionDatosProps) {
  const { asesor, sede } = contextoRadicacion()
  const [datos, setDatos] = useState<DatosRevisados>(() =>
    enMayusculas({
      ...valoresIniciales,
      ...mapearOCR(ocr),
      ...Object.fromEntries(
        Object.entries(inicial ?? {}).filter(
          ([, v]) => v !== undefined && v !== '',
        ),
      ),
    }),
  )
  const [dudososConfirmados, setDudososConfirmados] = useState<
    Record<string, boolean>
  >({})
  const [tocados, setTocados] = useState<Partial<Record<CampoId, boolean>>>({})
  const [intentado, setIntentado] = useState(false)
  const [registrado, setRegistrado] = useState(false)

  // Verificación de políticas clave: lo ya capturado (retomar o volver
  // desde el paso 4) prima; si no, se deduce del tipo de cédula del OCR.
  const politicasOCR = politicasDesdeOCR(ocr)
  const [nacionalidad, setNacionalidad] = useState<Nacionalidad | ''>(
    () =>
      nacionalidadDesdeApi(inicialPoliticas?.nacionalidad) ||
      politicasOCR.nacionalidad,
  )
  const documentos = nacionalidad
    ? DOCUMENTOS_POR_NACIONALIDAD[nacionalidad]
    : []
  const [tipoDocumento, setTipoDocumento] = useState(() => {
    const previo = inicialPoliticas?.tipoDocumento || politicasOCR.tipoDocumento
    return documentos.some((d) => d.codigo === previo) ? previo! : ''
  })
  const [simitConsultado, setSimitConsultado] = useState(false)
  const [multas, setMultas] = useState<'si' | 'no' | ''>(() =>
    inicialPoliticas?.multasPendientes === undefined
      ? ''
      : inicialPoliticas.multasPendientes
        ? 'si'
        : 'no',
  )
  const [politicasTocadas, setPoliticasTocadas] = useState<
    Partial<Record<CampoPolitica, boolean>>
  >({})
  const erroresPoliticas: Partial<Record<CampoPolitica, string>> = {
    ...(!nacionalidad && { nacionalidad: 'Selecciona la nacionalidad.' }),
    ...(!tipoDocumento && {
      tipoDocumento: 'Selecciona el tipo de documento.',
    }),
    ...(!multas && { multas: 'Selecciona una opción para continuar.' }),
    // La respuesta Sí/No debe salir de la consulta real en SIMIT.
    ...(!simitConsultado && {
      simit: 'Marca "Consultar" y revisa el SIMIT antes de continuar.',
    }),
  }
  const mostrarErrorPolitica = (campo: CampoPolitica) =>
    Boolean(erroresPoliticas[campo]) && (intentado || politicasTocadas[campo])
  const tocarPolitica = (campo: CampoPolitica) =>
    setPoliticasTocadas((prev) => ({ ...prev, [campo]: true }))

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

  // Nivel de confianza global: promedio de la confianza OCR de los campos
  // leídos (sin OCR, base neutra del 50 %); confirmar dudosos suma a 100.
  const confianzaOCR = useMemo(() => {
    const confianzas = camposBase
      .map((c) => campoOCR(ocr, c.id))
      .filter((c): c is CampoOCRApi => Boolean(c?.valor))
      .map((c) => c.confianza)
      .filter((c) => c > 0)
    if (confianzas.length === 0) return 50
    return confianzas.reduce((a, b) => a + b, 0) / confianzas.length
  }, [ocr])

  const camposDudosos = useMemo(() => campos.filter((c) => c.dudoso), [campos])

  const dudososConfirmadosCount = camposDudosos.filter(
    (c) => dudososConfirmados[c.id],
  ).length

  const bonusPorConfirmacion =
    camposDudosos.length > 0
      ? (CONFIANZA_MAXIMA - confianzaOCR) / camposDudosos.length
      : 0

  const confianzaActual = Math.min(
    CONFIANZA_MAXIMA,
    confianzaOCR + dudososConfirmadosCount * bonusPorConfirmacion,
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

    if (
      Object.keys(errores).length > 0 ||
      dudososPendientes.length > 0 ||
      Object.keys(erroresPoliticas).length > 0 ||
      !nacionalidad
    ) {
      setRegistrado(false)
      return
    }

    setRegistrado(true)
    onContinue?.(datos, {
      tipoDocumento,
      // La cédula y la fecha confirmadas aquí son la fuente de verdad.
      numeroDocumento: datos.numeroIdentificacion.replace(/\D/g, ''),
      fechaNacimiento: datos.fechaNacimiento,
      nacionalidad: NACIONALIDAD_API[nacionalidad],
      // Con multas el flujo radica la solicitud rechazada (R22) y termina.
      multasPendientes: multas === 'si',
    })
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
                <dt>Concesionario</dt>
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
            <h2>Datos extraídos</h2>
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

        <div className="revision__confianza" role="note">
          <div className="revision__confianza-copy">
            <span className="revision__confianza-label">
              Nivel de Confianza del Procesamiento
            </span>
            {camposDudosos.length > 0 && (
              <small>
                {dudososConfirmadosCount}/{camposDudosos.length} campo
                {camposDudosos.length > 1 ? 's' : ''} dudoso
                {camposDudosos.length > 1 ? 's' : ''} confirmado
                {dudososConfirmadosCount === 1 ? '' : 's'} manualmente.
              </small>
            )}
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
          <div
            className={`revision__field${mostrarErrorPolitica('nacionalidad') ? ' has-error' : ''}`}
          >
            <label htmlFor="rev-nacionalidad">
              Nacionalidad{' '}
              <span className="revision__required" aria-hidden="true">
                *
              </span>
            </label>
            <div className="revision__input-wrap">
              <select
                id="rev-nacionalidad"
                required
                value={nacionalidad}
                aria-invalid={mostrarErrorPolitica('nacionalidad')}
                onChange={(event) => {
                  setNacionalidad(event.target.value as Nacionalidad)
                  setTipoDocumento('')
                  tocarPolitica('nacionalidad')
                  setRegistrado(false)
                }}
                onBlur={() => tocarPolitica('nacionalidad')}
              >
                <option value="" disabled>
                  Selecciona la nacionalidad
                </option>
                {NACIONALIDADES.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
              <span className="revision__select-arrow" aria-hidden="true">
                ▾
              </span>
            </div>
            {mostrarErrorPolitica('nacionalidad') && (
              <p className="revision__error" role="alert">
                {erroresPoliticas.nacionalidad}
              </p>
            )}
          </div>

          <div
            className={`revision__field${mostrarErrorPolitica('tipoDocumento') ? ' has-error' : ''}`}
          >
            <label htmlFor="rev-tipo-documento">
              Tipo de Documento{' '}
              <span className="revision__required" aria-hidden="true">
                *
              </span>
            </label>
            <div className="revision__input-wrap">
              <select
                id="rev-tipo-documento"
                required
                value={tipoDocumento}
                aria-invalid={mostrarErrorPolitica('tipoDocumento')}
                onChange={(event) => {
                  setTipoDocumento(event.target.value)
                  tocarPolitica('tipoDocumento')
                  setRegistrado(false)
                }}
                onBlur={() => tocarPolitica('tipoDocumento')}
              >
                <option value="" disabled>
                  {nacionalidad
                    ? 'Selecciona el tipo de documento'
                    : 'Primero elige la nacionalidad'}
                </option>
                {documentos.map((doc) => (
                  <option key={doc.codigo} value={doc.codigo}>
                    {doc.nombre}
                  </option>
                ))}
              </select>
              <span className="revision__select-arrow" aria-hidden="true">
                ▾
              </span>
            </div>
            {mostrarErrorPolitica('tipoDocumento') ? (
              <p className="revision__error" role="alert">
                {erroresPoliticas.tipoDocumento}
              </p>
            ) : (
              documentos.length === 1 && (
                <p className="revision__hint">
                  Único documento aceptado para esta nacionalidad.
                </p>
              )
            )}
          </div>

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
                      actualizar(campo.id, event.target.value.toUpperCase())
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

          <div
            className={`revision__field revision__field--full${
              mostrarErrorPolitica('multas') ? ' has-error' : ''
            }`}
          >
            <span className="revision__label" id="rev-multas-label">
              ¿Tiene multas pendientes de pago?{' '}
              <span className="revision__required" aria-hidden="true">
                *
              </span>
            </span>
            <div className="revision__multas-controles">
              <label className="revision__consultar">
                <input
                  type="checkbox"
                  checked={simitConsultado}
                  onChange={(event) => {
                    setSimitConsultado(event.target.checked)
                    if (event.target.checked) abrirSimit()
                  }}
                />
                Consultar
              </label>
              <div
                className="revision__toggle"
                role="radiogroup"
                aria-labelledby="rev-multas-label"
              >
                {(['si', 'no'] as const).map((opcion) => (
                  <button
                    key={opcion}
                    type="button"
                    role="radio"
                    aria-checked={multas === opcion}
                    className={`revision__toggle-option${multas === opcion ? ' is-active' : ''}`}
                    onClick={() => {
                      setMultas(opcion)
                      tocarPolitica('multas')
                      setRegistrado(false)
                    }}
                  >
                    {opcion === 'si' ? 'Sí' : 'No'}
                  </button>
                ))}
              </div>
            </div>
            {mostrarErrorPolitica('simit') ? (
              <p className="revision__error" role="alert">
                {erroresPoliticas.simit}
              </p>
            ) : mostrarErrorPolitica('multas') ? (
              <p className="revision__error" role="alert">
                {erroresPoliticas.multas}
              </p>
            ) : multas === 'si' ? (
              <p className="revision__warning" role="status">
                La solicitud puede ser Rechazada: el cliente presenta multas
                pendientes.
              </p>
            ) : null}
          </div>
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
