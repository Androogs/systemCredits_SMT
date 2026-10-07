import { useMemo, useState, type FormEvent } from 'react'
import { ArrowLeft, ArrowRight } from 'lucide-react'
import Boton from '../../../shared/ui/Boton'
import { calcularCupoSugerido } from '../model/resultado-evaluacion'
import {
  construirCrearSolicitudPayload,
  type IdentidadSolicitante,
} from '../model/mapeos-api'
import { ApiError, crearSolicitud } from '../api/originacionApi'
import SeguimientoOriginacion from './SeguimientoOriginacion/SeguimientoOriginacion'
import './CrearSolicitud.css'

export interface DatosSolicitud {
  lineaCredito: string
  destinoCredito: string
  plazoMeses: number
  ocupacion: string
  empresa: string
  mesesContinuidad: number
  aniosCamara: number | null
  ingresosMensuales: number
  egresosMensuales: number
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

const plazosMeses = [12, 24, 36, 48]

const ocupaciones = [
  'Empleado Término Indefinido',
  'Empleado Término Fijo',
  'Independiente',
  'Pensionado',
  'Prestador de Servicios',
]

const valoresIniciales: DatosSolicitud = {
  lineaCredito: 'Inversiones Pacífico',
  destinoCredito: 'Financiamiento de Vehículos',
  plazoMeses: 36,
  ocupacion: '',
  empresa: '',
  mesesContinuidad: 24,
  aniosCamara: null,
  ingresosMensuales: 4_500_000,
  egresosMensuales: 1_800_000,
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

function soloDigitos(valor: string) {
  return valor.replace(/[^\d]/g, '')
}

function CrearSolicitud({
  onContinue,
  onBack,
  inicial,
  identidad,
}: CrearSolicitudProps) {
  const [datos, setDatos] = useState<DatosSolicitud>({
    ...valoresIniciales,
    ...inicial,
  })
  const [tocados, setTocados] = useState<Record<string, boolean>>({})
  const [intentado, setIntentado] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [registrado, setRegistrado] = useState(false)
  const [errorApi, setErrorApi] = useState<string | null>(null)

  const errores = useMemo(() => {
    const lista: Partial<Record<keyof DatosSolicitud, string>> = {}
    if (!datos.lineaCredito)
      lista.lineaCredito = 'Selecciona la línea de crédito.'
    if (!datos.destinoCredito)
      lista.destinoCredito = 'Selecciona el destino del crédito.'
    if (!datos.plazoMeses) lista.plazoMeses = 'Selecciona el plazo deseado.'
    if (!datos.ocupacion) lista.ocupacion = 'Selecciona la ocupación principal.'
    if (!datos.empresa.trim()) lista.empresa = 'Ingresa la empresa o empleador.'
    if (datos.mesesContinuidad < 0)
      lista.mesesContinuidad = 'La continuidad no puede ser negativa.'
    if (
      datos.ocupacion === 'Independiente' &&
      (datos.aniosCamara === null || datos.aniosCamara <= 0)
    )
      lista.aniosCamara =
        'Requerido para independientes: el motor rechaza sin Cámara de Comercio (R16).'
    else if (datos.aniosCamara !== null && datos.aniosCamara < 0)
      lista.aniosCamara = 'Los años de Cámara no pueden ser negativos.'
    if (!datos.ingresosMensuales || datos.ingresosMensuales <= 0)
      lista.ingresosMensuales = 'Ingresa los ingresos mensuales.'
    if (datos.egresosMensuales < 0)
      lista.egresosMensuales = 'Los egresos no pueden ser negativos.'
    return lista
  }, [datos])

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

  // ---------- Métricas derivadas ----------
  const disponibleMensual = Math.max(
    0,
    datos.ingresosMensuales - datos.egresosMensuales,
  )

  const capacidadEndeudamiento = useMemo(() => {
    if (datos.ingresosMensuales <= 0) return 0
    return Math.max(
      0,
      Math.round((disponibleMensual / datos.ingresosMensuales) * 100),
    )
  }, [datos.ingresosMensuales, disponibleMensual])

  const cupoReferencial = useMemo(
    () =>
      calcularCupoSugerido(
        datos.ingresosMensuales,
        datos.egresosMensuales,
        datos.plazoMeses || 1,
      ).monto,
    [datos.ingresosMensuales, datos.egresosMensuales, datos.plazoMeses],
  )

  const estadoCapacidad =
    capacidadEndeudamiento >= 40
      ? 'alta'
      : capacidadEndeudamiento >= 20
        ? 'media'
        : 'baja'

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
    crearSolicitud(construirCrearSolicitudPayload(identidad, datos))
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
          <p className="solicitud__eyebrow">Originación Individual · Paso 7</p>
          <h1>Crear Solicitud de Crédito</h1>
          <p className="solicitud__subtitle">Producto y perfil económico</p>
          <p className="solicitud__lede">
            Registra el producto y la información económica del solicitante. Con
            estos datos el motor evaluará la solicitud y sugerirá el cupo máximo
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
          <span className="solicitud__server">
            <span aria-hidden="true" />
            Servidor de Validación Activo v2.4.12-Prod (SSL)
          </span>
        </aside>
      </header>

      <SeguimientoOriginacion pasoActual={7} />

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
              <p>
                Línea, destino y plazo deseado. El monto lo sugiere el motor
                tras la evaluación.
              </p>
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

            <div
              className={`solicitud__field${
                mostrarError('plazoMeses') ? ' has-error' : ''
              }`}
            >
              <label htmlFor="sol-plazo">
                Plazo Deseado{' '}
                <span className="solicitud__required" aria-hidden="true">
                  *
                </span>
              </label>
              <div className="solicitud__input-wrap">
                <select
                  id="sol-plazo"
                  value={datos.plazoMeses}
                  aria-invalid={mostrarError('plazoMeses')}
                  onChange={(e) =>
                    actualizar('plazoMeses', Number(e.target.value))
                  }
                  onBlur={() => marcarTocado('plazoMeses')}
                >
                  {plazosMeses.map((meses) => (
                    <option key={meses} value={meses}>
                      {meses} Meses
                    </option>
                  ))}
                </select>
                <span className="solicitud__select-arrow" aria-hidden="true">
                  ▾
                </span>
              </div>
              {mostrarError('plazoMeses') && (
                <p className="solicitud__error" role="alert">
                  {errores.plazoMeses}
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
                  onChange={(e) => actualizar('ocupacion', e.target.value)}
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

            <div
              className={`solicitud__field${
                mostrarError('empresa') ? ' has-error' : ''
              }`}
            >
              <label htmlFor="sol-empresa">
                Empresa / Empleador{' '}
                <span className="solicitud__required" aria-hidden="true">
                  *
                </span>
              </label>
              <input
                id="sol-empresa"
                type="text"
                autoComplete="organization"
                placeholder="Nombre de la empresa"
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
              <input
                id="sol-continuidad"
                type="text"
                inputMode="numeric"
                value={datos.mesesContinuidad.toLocaleString('es-CO')}
                aria-invalid={mostrarError('mesesContinuidad')}
                onChange={(e) =>
                  actualizar(
                    'mesesContinuidad',
                    Number(soloDigitos(e.target.value)),
                  )
                }
                onBlur={() => marcarTocado('mesesContinuidad')}
              />
              {mostrarError('mesesContinuidad') && (
                <p className="solicitud__error" role="alert">
                  {errores.mesesContinuidad}
                </p>
              )}
            </div>

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
                <input
                  id="sol-camara"
                  type="text"
                  inputMode="decimal"
                  placeholder="Ej. 3.5"
                  value={datos.aniosCamara ?? ''}
                  aria-invalid={mostrarError('aniosCamara')}
                  onChange={(e) => {
                    const texto = e.target.value.replace(',', '.')
                    actualizar(
                      'aniosCamara',
                      texto === '' ? null : Number(texto),
                    )
                  }}
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
                <input
                  id="sol-ingresos"
                  type="text"
                  inputMode="numeric"
                  value={datos.ingresosMensuales.toLocaleString('es-CO')}
                  aria-invalid={mostrarError('ingresosMensuales')}
                  onChange={(e) =>
                    actualizar(
                      'ingresosMensuales',
                      Number(soloDigitos(e.target.value)),
                    )
                  }
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

            <div
              className={`solicitud__field${
                mostrarError('egresosMensuales') ? ' has-error' : ''
              }`}
            >
              <label htmlFor="sol-egresos">
                Egresos / Gastos Mensuales{' '}
                <span className="solicitud__required" aria-hidden="true">
                  *
                </span>
              </label>
              <div className="solicitud__input-wrap solicitud__input-wrap--money">
                <span className="solicitud__prefix" aria-hidden="true">
                  $
                </span>
                <input
                  id="sol-egresos"
                  type="text"
                  inputMode="numeric"
                  value={datos.egresosMensuales.toLocaleString('es-CO')}
                  aria-invalid={mostrarError('egresosMensuales')}
                  onChange={(e) =>
                    actualizar(
                      'egresosMensuales',
                      Number(soloDigitos(e.target.value)),
                    )
                  }
                  onBlur={() => marcarTocado('egresosMensuales')}
                />
                <span className="solicitud__suffix" aria-hidden="true">
                  COP
                </span>
              </div>
              {mostrarError('egresosMensuales') && (
                <p className="solicitud__error" role="alert">
                  {errores.egresosMensuales}
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
              <h3>Análisis de Capacidad</h3>
              <span className="solicitud__analisis-hint">
                Estimación automática · no vinculante
              </span>
            </div>

            <div className="solicitud__analisis-grid">
              <div className="solicitud__analisis-card">
                <span className="solicitud__analisis-label">
                  Disponible mensual
                </span>
                <strong className="solicitud__analisis-valor">
                  {formatoCOP.format(disponibleMensual)}
                </strong>
                <small>Ingresos menos egresos declarados</small>
              </div>

              <div
                className={`solicitud__analisis-card solicitud__analisis-card--${estadoCapacidad}`}
              >
                <span className="solicitud__analisis-label">
                  Capacidad de endeudamiento
                </span>
                <strong className="solicitud__analisis-valor">
                  {capacidadEndeudamiento}%
                </strong>
                <small>
                  {estadoCapacidad === 'alta' && 'Dentro del rango recomendado'}
                  {estadoCapacidad === 'media' &&
                    'Cercano al límite prudencial'}
                  {estadoCapacidad === 'baja' && 'Capacidad limitada'}
                </small>
              </div>

              <div className="solicitud__analisis-card">
                <span className="solicitud__analisis-label">
                  Cupo estimado referencial
                </span>
                <strong className="solicitud__analisis-valor">
                  {formatoCOPCompacto(cupoReferencial)}
                </strong>
                <small>
                  El monto final lo sugiere el motor tras la evaluación
                </small>
              </div>
            </div>
          </aside>
        </section>

        {/* ------------ Resultado Final ------------ */}
        <section
          className="solicitud__final"
          aria-label="Resultado final del proceso"
        >
          <span className="solicitud__final-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" focusable="false">
              <path
                d="M4 19V5a1 1 0 0 1 1-1h11l4 4v11a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1Z"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.7"
                strokeLinejoin="round"
              />
              <path
                d="M8 12h8M8 16h5"
                stroke="currentColor"
                strokeWidth="1.7"
                strokeLinecap="round"
              />
            </svg>
          </span>
          <div className="solicitud__final-copy">
            <span className="solicitud__final-eyebrow">Resultado Final</span>
            <strong>Firma y desembolso</strong>
            <p>
              Al registrar la solicitud, el proceso continúa con la etapa de
              firma del pagaré y el desembolso del crédito.
            </p>
          </div>
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
                Volver al paso 6
              </Boton>
            )}
            <p className="solicitud__actions-note">
              <span className="solicitud__dot" aria-hidden="true" />
              {registrado
                ? 'Solicitud lista para firma.'
                : 'Verifica los datos antes de registrar.'}
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
                : 'Registrar Solicitud'}
          </Boton>
        </div>
      </form>
    </div>
  )
}

export default CrearSolicitud
