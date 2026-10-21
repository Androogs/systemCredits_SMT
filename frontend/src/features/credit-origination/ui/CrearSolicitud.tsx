import { useMemo, useState, type FormEvent } from 'react'
import { ArrowLeft, ArrowRight } from 'lucide-react'
import Boton from '../../../shared/ui/Boton'
import CampoNumerico from '../../../shared/ui/CampoNumerico'
import { calcularCupoSugerido } from '../model/resultado-evaluacion'
import {
  construirCrearSolicitudPayload,
  type IdentidadSolicitante,
} from '../model/mapeos-api'
import {
  ApiError,
  actualizarSolicitud,
  crearSolicitud,
} from '../api/originacionApi'
import { erroresSolicitud } from '../model/solicitud-schema'
import {
  OCUPACIONES,
  TIPOS_CONTRATO,
  SUBTIPOS_INDEPENDIENTE,
  ENTIDADES_PENSION,
  INSTITUCIONES_FUERZAS,
} from '../schemas/laboral'
import SeguimientoOriginacion from './SeguimientoOriginacion/SeguimientoOriginacion'
import './CrearSolicitud.css'

export interface DatosSolicitud {
  lineaCredito: string
  destinoCredito: string
  plazoMeses: number
  ocupacion: string
  /** Solo cuando ocupacion === 'Empleado' (Indefinido/Fijo/Obra o Labor). */
  tipoContrato: string
  /** Solo cuando ocupacion === 'Independiente'. */
  subtipoIndependiente: string
  empresa: string
  /** Solo cuando ocupacion === 'Empleado'. */
  mesesContinuidad: number
  aniosCamara: number | null
  ingresosMensuales: number
  /** Fondo de pensiones / fuerza / institución según ocupación. */
  entidadPagadora: string
}

export interface ResultadoCrearSolicitud {
  datos: DatosSolicitud
  /** Presente cuando la solicitud quedó persistida en el backend. */
  idSolicitud?: string
}

interface CrearSolicitudProps {
  onContinue?: (resultado: ResultadoCrearSolicitud) => void
  onBack?: () => void
  /** Datos pre-cargados desde los pasos anteriores. */
  inicial?: Partial<DatosSolicitud>
  /** Identidad capturada en los pasos 1-6 (habilita el POST real). */
  identidad?: IdentidadSolicitante
  /** Token de la sesión de captura del paso 3: enlaza las evidencias. */
  sesionCapturaToken?: string
  /** Solicitud ya radicada que se retoma: el guardado actualiza (PUT)
   * en vez de duplicar la radicación. */
  idSolicitud?: string
}

const lineasCredito = [
  'Inversiones Pacífico',
  'Libre Inversión',
  'Vivienda Pacífico',
  'Educación Pacífico',
]

const destinosCredito = [
  'Financiamiento de Vehículos',
  'Capital de Trabajo',
  'Libre Destino',
  'Mejoras de Vivienda',
  'Consolidación de Deudas',
]

// Fuente única: OCUPACIONES del schema laboral (validación y select
// no pueden quedar desincronizados).
const ocupaciones = OCUPACIONES
const subtiposIndependiente = SUBTIPOS_INDEPENDIENTE
const entidadesPension = ENTIDADES_PENSION
const institucionesFuerzas = INSTITUCIONES_FUERZAS

// Borradores guardados con el selector anterior (6 opciones) se
// normalizan al esquema nuevo de 4 ocupaciones + tipo de contrato.
const OCUPACION_LEGACY: Record<
  string,
  Pick<DatosSolicitud, 'ocupacion' | 'tipoContrato'>
> = {
  'Empleado Término Indefinido': {
    ocupacion: 'Empleado',
    tipoContrato: 'Indefinido',
  },
  'Empleado Término Fijo': { ocupacion: 'Empleado', tipoContrato: 'Fijo' },
  'Prestador de Servicios': {
    ocupacion: 'Empleado',
    tipoContrato: 'Obra o Labor',
  },
}

function normalizarOcupacion(
  parcial: Partial<DatosSolicitud> | undefined,
): Partial<DatosSolicitud> {
  if (!parcial?.ocupacion) return parcial ?? {}
  const legado = OCUPACION_LEGACY[parcial.ocupacion]
  return legado ? { ...parcial, ...legado } : parcial
}

const PLAZO_FIJO_MESES = 24

// Precarga de demostración solo en dev (import.meta.env.DEV); en el
// build de producción los campos económicos arrancan vacíos.
const valoresIniciales: DatosSolicitud = import.meta.env.DEV
  ? {
      lineaCredito: 'Inversiones Pacífico',
      destinoCredito: 'Financiamiento de Vehículos',
      plazoMeses: PLAZO_FIJO_MESES,
      ocupacion: 'Empleado',
      tipoContrato: 'Indefinido',
      subtipoIndependiente: '',
      empresa: 'Inversiones Pacífico',
      mesesContinuidad: 24,
      aniosCamara: null,
      ingresosMensuales: 4_500_000,
      entidadPagadora: '',
    }
  : {
      lineaCredito: 'Inversiones Pacífico',
      destinoCredito: 'Financiamiento de Vehículos',
      plazoMeses: PLAZO_FIJO_MESES,
      ocupacion: '',
      tipoContrato: '',
      subtipoIndependiente: '',
      empresa: '',
      mesesContinuidad: 0,
      aniosCamara: null,
      ingresosMensuales: 0,
      entidadPagadora: '',
    }

const EMPLEADOR_LABELS: Record<string, { label: string; placeholder: string }> =
  {
    Empleado: {
      label: 'Empresa / Empleador',
      placeholder: 'Ej. Inversiones Pacífico',
    },
    Independiente: {
      label: 'Negocio o actividad',
      placeholder: 'Ej. Tienda de barrio, consultoría…',
    },
    Pensionado: {
      label: 'Entidad pagadora / fondo de pensiones',
      placeholder: 'Ej. Colpensiones, Protección…',
    },
    'Fuerzas Militares': {
      label: 'Fuerza o institución',
      placeholder: 'Ej. Ejército Nacional, Policía Nacional…',
    },
  }

const formatoCOP = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
})

const formatoCOPCompacto = (valor: number) => {
  if (valor >= 1_000_000) {
    return `$${(valor / 1_000_000).toFixed(valor % 1_000_000 === 0 ? 0 : 1)}M`
  }
  if (valor >= 1_000) {
    return `$${(valor / 1_000).toFixed(0)}K`
  }
  return `$${valor}`
}

function CrearSolicitud({
  onContinue,
  onBack,
  inicial,
  identidad,
  sesionCapturaToken,
  idSolicitud,
}: CrearSolicitudProps) {
  const [datos, setDatos] = useState<DatosSolicitud>({
    ...valoresIniciales,
    ...normalizarOcupacion(inicial),
  })
  const [tocados, setTocados] = useState<Record<string, boolean>>({})
  const [intentado, setIntentado] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [registrado, setRegistrado] = useState(false)
  const [errorApi, setErrorApi] = useState<string | null>(null)

  const errores = useMemo(() => erroresSolicitud(datos), [datos])

  const mostrarError = (campo: keyof DatosSolicitud) =>
    Boolean(errores[campo]) && (intentado || tocados[campo])

  const marcarTocado = (campo: keyof DatosSolicitud) =>
    setTocados((prev) => ({ ...prev, [campo]: true }))

  const actualizar = <K extends keyof DatosSolicitud>(
    campo: K,
    valor: DatosSolicitud[K],
  ) => {
    setDatos((prev) => ({ ...prev, [campo]: valor }))
    setRegistrado(false)
  }

  // ---------- Métricas derivadas (fórmula del motor) ----------
  const capacidad = useMemo(
    () =>
      calcularCupoSugerido(
        datos.ingresosMensuales,
        datos.plazoMeses || PLAZO_FIJO_MESES,
      ),
    [datos.ingresosMensuales, datos.plazoMeses],
  )

  const continuarDemo = () => {
    setRegistrado(true)
    onContinue?.({ datos })
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setIntentado(true)

    if (Object.keys(errores).length > 0) {
      setRegistrado(false)
      return
    }

    if (!identidad) {
      continuarDemo()
      return
    }

    setEnviando(true)
    setErrorApi(null)
    const payload = construirCrearSolicitudPayload(
      identidad,
      datos,
      sesionCapturaToken,
    )
    // Solicitud retomada: actualiza el registro persistido; una nueva
    // radicación la crearía duplicada.
    const persistir = idSolicitud
      ? actualizarSolicitud(idSolicitud, payload)
      : crearSolicitud(payload)
    persistir
      .then((respuesta) => {
        setEnviando(false)
        setRegistrado(true)
        onContinue?.({ datos, idSolicitud: respuesta.id_solicitud })
      })
      .catch((err: unknown) => {
        setEnviando(false)
        const detalle =
          err instanceof ApiError && err.detalle
            ? ` (${typeof err.detalle === 'string' ? err.detalle : JSON.stringify(err.detalle)})`
            : ''
        setErrorApi(
          `No se pudo registrar la solicitud en el backend${detalle}. Reintenta o continúa en modo demostración.`,
        )
      })
  }

  return (
    <div className="solicitud">
      <header className="solicitud__header">
        <div className="solicitud__header-copy">
          <p className="solicitud__eyebrow">Originación Individual · Paso 4</p>
          <h1>Perfil económico del solicitante</h1>
          <p className="solicitud__subtitle">Producto, ocupación y capacidad</p>
          <p className="solicitud__lede">
            Registra el producto y la información económica del solicitante. Con
            estos datos se evaluará la solicitud y se sugerirá el cupo máximo
            que el cliente podrá tomar.
          </p>
        </div>

        <aside
          className="solicitud__panel"
          aria-label="Contexto de la radicación"
        >
          <dl className="solicitud__meta">
            <div>
              <dt>Asesor</dt>
              <dd>Carlos Mendoza</dd>
            </div>
            <div>
              <dt>Sede</dt>
              <dd>Palmira - Centro Interno</dd>
            </div>
          </dl>
        </aside>
      </header>

      <SeguimientoOriginacion pasoActual={4} />

      <form className="solicitud__form" onSubmit={handleSubmit} noValidate>
        {registrado && (
          <div
            className="solicitud__banner solicitud__banner--ok"
            role="status"
          >
            <strong>Solicitud registrada correctamente.</strong>
            <span>
              Pasa a la etapa de <strong>Firma y desembolso</strong> para
              completar el proceso.
            </span>
          </div>
        )}

        {errorApi && (
          <div
            className="solicitud__banner solicitud__banner--error"
            role="alert"
          >
            <strong>Error de conexión.</strong>
            <span>{errorApi}</span>
            <button
              type="button"
              className="solicitud__banner-demo"
              onClick={continuarDemo}
            >
              Continuar en modo demostración
            </button>
          </div>
        )}

        {/* ------------ 1. Configuración de Producto Financiero ------------ */}
        <section
          className="solicitud__section"
          aria-labelledby="solicitud-sec-1"
        >
          <header className="solicitud__section-head">
            <span className="solicitud__section-num" aria-hidden="true">
              1
            </span>
            <div>
              <h2 id="solicitud-sec-1">Configuración de Producto Financiero</h2>
              <p>Línea y destino. El monto se sugiere tras la evaluación.</p>
            </div>
          </header>

          <div className="solicitud__grid">
            <div
              className={`solicitud__field${
                mostrarError('lineaCredito') ? ' has-error' : ''
              }`}
            >
              <label htmlFor="sol-linea">
                Línea de Crédito{' '}
                <span className="solicitud__required" aria-hidden="true">
                  *
                </span>
              </label>
              <div className="solicitud__input-wrap">
                <select
                  id="sol-linea"
                  value={datos.lineaCredito}
                  aria-invalid={mostrarError('lineaCredito')}
                  onChange={(e) => actualizar('lineaCredito', e.target.value)}
                  onBlur={() => marcarTocado('lineaCredito')}
                >
                  {lineasCredito.map((opcion) => (
                    <option key={opcion} value={opcion}>
                      {opcion}
                    </option>
                  ))}
                </select>
                <span className="solicitud__select-arrow" aria-hidden="true">
                  ▾
                </span>
              </div>
              {mostrarError('lineaCredito') && (
                <p className="solicitud__error" role="alert">
                  {errores.lineaCredito}
                </p>
              )}
            </div>

            <div
              className={`solicitud__field${
                mostrarError('destinoCredito') ? ' has-error' : ''
              }`}
            >
              <label htmlFor="sol-destino">
                Destino del Crédito{' '}
                <span className="solicitud__required" aria-hidden="true">
                  *
                </span>
              </label>
              <div className="solicitud__input-wrap">
                <select
                  id="sol-destino"
                  value={datos.destinoCredito}
                  aria-invalid={mostrarError('destinoCredito')}
                  onChange={(e) => actualizar('destinoCredito', e.target.value)}
                  onBlur={() => marcarTocado('destinoCredito')}
                >
                  {destinosCredito.map((opcion) => (
                    <option key={opcion} value={opcion}>
                      {opcion}
                    </option>
                  ))}
                </select>
                <span className="solicitud__select-arrow" aria-hidden="true">
                  ▾
                </span>
              </div>
              {mostrarError('destinoCredito') && (
                <p className="solicitud__error" role="alert">
                  {errores.destinoCredito}
                </p>
              )}
            </div>
          </div>
        </section>

        {/* ------------ 2. Información Económica del Solicitante ------------ */}
        <section
          className="solicitud__section"
          aria-labelledby="solicitud-sec-2"
        >
          <header className="solicitud__section-head">
            <span className="solicitud__section-num" aria-hidden="true">
              2
            </span>
            <div>
              <h2 id="solicitud-sec-2">
                Información Económica del Solicitante
              </h2>
              <p>
                Datos declarados por el cliente para el análisis de capacidad.
              </p>
            </div>
          </header>

          <div className="solicitud__grid">
            <div
              className={`solicitud__field${
                mostrarError('ocupacion') ? ' has-error' : ''
              }`}
            >
              <label htmlFor="sol-ocupacion">
                Ocupación Principal{' '}
                <span className="solicitud__required" aria-hidden="true">
                  *
                </span>
              </label>
              <div className="solicitud__input-wrap">
                <select
                  id="sol-ocupacion"
                  value={datos.ocupacion}
                  aria-invalid={mostrarError('ocupacion')}
                  onChange={(e) => {
                    const ocupacion = e.target.value
                    setDatos((prev) => ({
                      ...prev,
                      ocupacion,
                      // Los campos condicionales se limpian al cambiar
                      // de ocupación para no arrastrar datos ajenos.
                      tipoContrato:
                        ocupacion === 'Empleado' ? prev.tipoContrato : '',
                      mesesContinuidad:
                        ocupacion === 'Empleado' ? prev.mesesContinuidad : 0,
                      subtipoIndependiente:
                        ocupacion === 'Independiente'
                          ? prev.subtipoIndependiente
                          : '',
                      aniosCamara:
                        ocupacion === 'Independiente' ? prev.aniosCamara : null,
                      entidadPagadora:
                        ocupacion === 'Pensionado' ||
                        ocupacion === 'Fuerzas Militares'
                          ? prev.entidadPagadora
                          : '',
                    }))
                    setRegistrado(false)
                  }}
                  onBlur={() => marcarTocado('ocupacion')}
                >
                  <option value="" disabled>
                    Selecciona la ocupación…
                  </option>
                  {ocupaciones.map((opcion) => (
                    <option key={opcion} value={opcion}>
                      {opcion}
                    </option>
                  ))}
                </select>
                <span className="solicitud__select-arrow" aria-hidden="true">
                  ▾
                </span>
              </div>
              {mostrarError('ocupacion') && (
                <p className="solicitud__error" role="alert">
                  {errores.ocupacion}
                </p>
              )}
            </div>

            {datos.ocupacion === 'Empleado' && (
              <div
                className={`solicitud__field${
                  mostrarError('tipoContrato') ? ' has-error' : ''
                }`}
              >
                <label htmlFor="sol-contrato">
                  Tipo de contrato{' '}
                  <span className="solicitud__required" aria-hidden="true">
                    *
                  </span>
                </label>
                <div className="solicitud__input-wrap">
                  <select
                    id="sol-contrato"
                    value={datos.tipoContrato}
                    aria-invalid={mostrarError('tipoContrato')}
                    onChange={(e) => actualizar('tipoContrato', e.target.value)}
                    onBlur={() => marcarTocado('tipoContrato')}
                  >
                    <option value="" disabled>
                      Selecciona el contrato…
                    </option>
                    {TIPOS_CONTRATO.map((opcion) => (
                      <option key={opcion} value={opcion}>
                        {opcion}
                      </option>
                    ))}
                  </select>
                  <span className="solicitud__select-arrow" aria-hidden="true">
                    ▾
                  </span>
                </div>
                {mostrarError('tipoContrato') && (
                  <p className="solicitud__error" role="alert">
                    {errores.tipoContrato}
                  </p>
                )}
              </div>
            )}

            {datos.ocupacion === 'Independiente' && (
              <div
                className={`solicitud__field${
                  mostrarError('subtipoIndependiente') ? ' has-error' : ''
                }`}
              >
                <label htmlFor="sol-subtipo">
                  Tipo de independiente{' '}
                  <span className="solicitud__required" aria-hidden="true">
                    *
                  </span>
                </label>
                <div className="solicitud__input-wrap">
                  <select
                    id="sol-subtipo"
                    value={datos.subtipoIndependiente}
                    aria-invalid={mostrarError('subtipoIndependiente')}
                    onChange={(e) =>
                      actualizar('subtipoIndependiente', e.target.value)
                    }
                    onBlur={() => marcarTocado('subtipoIndependiente')}
                  >
                    <option value="" disabled>
                      Selecciona el tipo…
                    </option>
                    {subtiposIndependiente.map((opcion) => (
                      <option key={opcion} value={opcion}>
                        {opcion}
                      </option>
                    ))}
                  </select>
                  <span className="solicitud__select-arrow" aria-hidden="true">
                    ▾
                  </span>
                </div>
                {mostrarError('subtipoIndependiente') && (
                  <p className="solicitud__error" role="alert">
                    {errores.subtipoIndependiente}
                  </p>
                )}
              </div>
            )}

            {datos.ocupacion !== 'Pensionado' &&
              datos.ocupacion !== 'Fuerzas Militares' && (
                <div
                  className={`solicitud__field${
                    mostrarError('empresa') ? ' has-error' : ''
                  }`}
                >
                  <label htmlFor="sol-empresa">
                    {
                      (
                        EMPLEADOR_LABELS[datos.ocupacion] ??
                        EMPLEADOR_LABELS.Empleado
                      ).label
                    }{' '}
                    <span className="solicitud__required" aria-hidden="true">
                      *
                    </span>
                  </label>
                  <input
                    id="sol-empresa"
                    type="text"
                    autoComplete="organization"
                    placeholder={
                      (
                        EMPLEADOR_LABELS[datos.ocupacion] ??
                        EMPLEADOR_LABELS.Empleado
                      ).placeholder
                    }
                    value={datos.empresa}
                    aria-invalid={mostrarError('empresa')}
                    onChange={(e) => actualizar('empresa', e.target.value)}
                    onBlur={() => marcarTocado('empresa')}
                  />
                  {mostrarError('empresa') && (
                    <p className="solicitud__error" role="alert">
                      {errores.empresa}
                    </p>
                  )}
                </div>
              )}

            {datos.ocupacion === 'Empleado' && (
              <div
                className={`solicitud__field${
                  mostrarError('mesesContinuidad') ? ' has-error' : ''
                }`}
              >
                <label htmlFor="sol-continuidad">
                  Meses de continuidad laboral{' '}
                  <span className="solicitud__required" aria-hidden="true">
                    *
                  </span>
                </label>
                <CampoNumerico
                  id="sol-continuidad"
                  formatoMiles
                  minimo={0}
                  maximo={600}
                  value={datos.mesesContinuidad}
                  aria-invalid={mostrarError('mesesContinuidad')}
                  onValor={(n) => actualizar('mesesContinuidad', n ?? 0)}
                  onBlur={() => marcarTocado('mesesContinuidad')}
                />
                {mostrarError('mesesContinuidad') && (
                  <p className="solicitud__error" role="alert">
                    {errores.mesesContinuidad}
                  </p>
                )}
              </div>
            )}

            {(datos.ocupacion === 'Pensionado' ||
              datos.ocupacion === 'Fuerzas Militares') && (
              <div
                className={`solicitud__field${
                  mostrarError('entidadPagadora') ? ' has-error' : ''
                }`}
              >
                <label htmlFor="sol-entidad">
                  {datos.ocupacion === 'Pensionado'
                    ? 'Fondo de pensiones / entidad pagadora'
                    : 'Fuerza o institución'}{' '}
                  <span className="solicitud__required" aria-hidden="true">
                    *
                  </span>
                </label>
                <div className="solicitud__input-wrap">
                  <select
                    id="sol-entidad"
                    value={datos.entidadPagadora}
                    aria-invalid={mostrarError('entidadPagadora')}
                    onChange={(e) =>
                      actualizar('entidadPagadora', e.target.value)
                    }
                    onBlur={() => marcarTocado('entidadPagadora')}
                  >
                    <option value="" disabled>
                      Selecciona…
                    </option>
                    {(datos.ocupacion === 'Pensionado'
                      ? entidadesPension
                      : institucionesFuerzas
                    ).map((opcion) => (
                      <option key={opcion} value={opcion}>
                        {opcion}
                      </option>
                    ))}
                  </select>
                  <span className="solicitud__select-arrow" aria-hidden="true">
                    ▾
                  </span>
                </div>
                {mostrarError('entidadPagadora') && (
                  <p className="solicitud__error" role="alert">
                    {errores.entidadPagadora}
                  </p>
                )}
              </div>
            )}

            {datos.ocupacion === 'Independiente' && (
              <div
                className={`solicitud__field${
                  mostrarError('aniosCamara') ? ' has-error' : ''
                }`}
              >
                <label htmlFor="sol-camara">
                  Años con Cámara de Comercio{' '}
                  <span className="solicitud__required" aria-hidden="true">
                    *
                  </span>
                </label>
                <CampoNumerico
                  id="sol-camara"
                  decimales
                  placeholder="Ej. 3.5"
                  minimo={0}
                  maximo={100}
                  value={datos.aniosCamara}
                  aria-invalid={mostrarError('aniosCamara')}
                  onValor={(n) => actualizar('aniosCamara', n)}
                  onBlur={() => marcarTocado('aniosCamara')}
                />
                {mostrarError('aniosCamara') && (
                  <p className="solicitud__error" role="alert">
                    {errores.aniosCamara}
                  </p>
                )}
              </div>
            )}

            <div
              className={`solicitud__field${
                mostrarError('ingresosMensuales') ? ' has-error' : ''
              }`}
            >
              <label htmlFor="sol-ingresos">
                Ingresos Mensuales Certificados{' '}
                <span className="solicitud__required" aria-hidden="true">
                  *
                </span>
              </label>
              <div className="solicitud__input-wrap solicitud__input-wrap--money">
                <span className="solicitud__prefix" aria-hidden="true">
                  $
                </span>
                <CampoNumerico
                  id="sol-ingresos"
                  formatoMiles
                  minimo={0}
                  maximo={500_000_000}
                  value={datos.ingresosMensuales}
                  aria-invalid={mostrarError('ingresosMensuales')}
                  onValor={(n) => actualizar('ingresosMensuales', n ?? 0)}
                  onBlur={() => marcarTocado('ingresosMensuales')}
                />
                <span className="solicitud__suffix" aria-hidden="true">
                  COP
                </span>
              </div>
              {mostrarError('ingresosMensuales') && (
                <p className="solicitud__error" role="alert">
                  {errores.ingresosMensuales}
                </p>
              )}
            </div>
          </div>

          {/* Panel de análisis económico */}
          <aside
            className="solicitud__analisis"
            aria-label="Análisis económico"
          >
            <div className="solicitud__analisis-head">
              <h3>Capacidad de pago estimada</h3>
              <span className="solicitud__analisis-hint">
                Cálculo estimado · no vinculante
              </span>
            </div>

            <div className="solicitud__analisis-grid">
              <div className="solicitud__analisis-card solicitud__analisis-card--destacado">
                <span className="solicitud__analisis-label">
                  Cupo estimado a {PLAZO_FIJO_MESES} meses
                </span>
                <strong className="solicitud__analisis-valor">
                  {formatoCOPCompacto(capacidad.monto)}
                </strong>
                <small>Tope $20M · se define tras la evaluación</small>
              </div>

              <div className="solicitud__analisis-card solicitud__analisis-card--primary">
                <span className="solicitud__analisis-label">
                  Capacidad de pago
                </span>
                <strong className="solicitud__analisis-valor">
                  {formatoCOP.format(capacidad.capacidad)}
                </strong>
                <small>70% del disponible estimado</small>
              </div>

              <div className="solicitud__analisis-card">
                <span className="solicitud__analisis-label">
                  Disponible estimado
                </span>
                <strong className="solicitud__analisis-valor">
                  {formatoCOP.format(capacidad.disponible)}
                </strong>
                <small>Ingreso menos gastos personales</small>
              </div>

              <div className="solicitud__analisis-card">
                <span className="solicitud__analisis-label">
                  Gastos personales
                </span>
                <strong className="solicitud__analisis-valor">
                  {formatoCOP.format(capacidad.gastosPersonales)}
                </strong>
                <small>Según bandas de SMMLV</small>
              </div>
            </div>
          </aside>
        </section>

        <div className="solicitud__actions">
          <div className="solicitud__actions-left">
            {onBack && (
              <Boton
                variante="secundario"
                tamano="compacto"
                iconoInicio={<ArrowLeft size={15} aria-hidden="true" />}
                onClick={onBack}
                disabled={enviando || registrado}
              >
                Volver al paso 3
              </Boton>
            )}
            <p className="solicitud__actions-note">
              <span className="solicitud__dot" aria-hidden="true" />
              {registrado
                ? 'Solicitud lista para evaluación.'
                : 'Verifica los datos antes de enviar a evaluación.'}
            </p>
          </div>
          <Boton
            type="submit"
            cargando={enviando}
            disabled={enviando || registrado}
            iconoFin={
              !enviando && !registrado ? (
                <ArrowRight size={16} aria-hidden="true" />
              ) : undefined
            }
          >
            {enviando
              ? 'Registrando…'
              : registrado
                ? 'Solicitud registrada'
                : 'Continuar a evaluación'}
          </Boton>
        </div>
      </form>
    </div>
  )
}

export default CrearSolicitud
