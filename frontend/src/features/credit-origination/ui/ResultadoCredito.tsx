import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowLeft,
  BadgeCheck,
  Bike,
  Check,
  CircleAlert,
  Clock3,
  FileSearch,
  XCircle,
} from 'lucide-react'
import { currency } from '../../../shared/lib/formatters'
import { cuotaAnualidad } from '../../../shared/lib/finanzas'
import { useCuentaAscendente } from '../../../shared/lib/useCuentaAscendente'
import {
  guardarConcesionario,
  marcaDeConcesionario,
  obtenerConcesionario,
  useRol,
} from '../../../shared/lib/sesion'
import { emitirToast } from '../../../shared/lib/toastBus'
import Alerta from '../../../shared/ui/Alerta'
import CampoNumerico from '../../../shared/ui/CampoNumerico'
import type { ResultadoEvaluacionCredito } from '../model/resultado-evaluacion'
import { CONCESIONARIOS, MARCAS_VEHICULO } from '../model/concesionarios'
import {
  enviarAEstudio,
  obtenerOfertas,
  seleccionarOferta,
  type OfertaApi,
} from '../api/originacionApi'
import SeguimientoOriginacion from './SeguimientoOriginacion/SeguimientoOriginacion'
import CabeceraEtapaOriginacion from './CabeceraEtapaOriginacion'
import './CabeceraEtapaOriginacion.css'
import './ResultadoCredito.css'

export interface OfertaSeleccionada {
  monto: number
  plazoMeses: number
  cuotaMensual: number
  desembolsoEstimado: number
  /** Presente cuando la oferta quedó confirmada en el backend. */
  idOferta?: number
}

interface ResultadoCreditoProps {
  resultado: ResultadoEvaluacionCredito
  /** ID de la solicitud persistida (habilita ofertas y selección reales). */
  idSolicitud?: string
  formalizacionIniciada: boolean
  onModificar: () => void
  onFormalizar: (oferta: OfertaSeleccionada) => void
  /** Avisa cuando la solicitud quedó escalada a estudio del comité. */
  onEnviadaEstudio?: () => void
  /** Si es true, no renderiza cabecera ni seguimiento (para usar dentro de otro paso). */
  compacto?: boolean
}

// Piezas de confetti deterministas para celebrar la aprobación.
const CONFETTI: CSSProperties[] = Array.from({ length: 26 }, (_, i) => {
  const paleta = [
    '#22c55e',
    '#099dd7',
    '#f59e0b',
    '#f472b6',
    '#38bdf8',
    '#a3e635',
  ]
  return {
    '--x': `${(i * 37 + 13) % 100}%`,
    '--s': `${6 + (i % 4) * 2}px`,
    '--c': paleta[i % paleta.length],
    '--d': `${(2.1 + (i % 5) * 0.4).toFixed(2)}s`,
    '--dl': `${((i * 0.11) % 1.7).toFixed(2)}s`,
    '--dx': `${((i % 7) - 3) * 16}px`,
    '--r': i % 3 === 0 ? '50%' : '1.5px',
  } as CSSProperties
})

function ResultadoCredito({
  resultado,
  idSolicitud,
  formalizacionIniciada,
  onModificar,
  onFormalizar,
  onEnviadaEstudio,
  compacto = false,
}: ResultadoCreditoProps) {
  const aprobado = resultado.decision === 'APROBADO'
  const rechazado = resultado.decision === 'RECHAZADO'
  // Las causales de la decisión son dato sensible: solo el administrador.
  const esAsesor = useRol() === 'asesor'
  // Vista binaria del asesor: la revisión manual del motor (perfil gris)
  // se muestra como "no aprobado"; la revisión del comité es interna.
  const revisionManual = !aprobado && !rechazado
  const rechazadoVisible = rechazado || (esAsesor && revisionManual)

  const [ofertas, setOfertas] = useState<OfertaApi[]>([])
  const [errorOfertas, setErrorOfertas] = useState<string | null>(null)
  const [confirmando, setConfirmando] = useState(false)
  // true cuando el asesor escaló el rechazo a revisión del comité.
  const [enEstudio, setEnEstudio] = useState(false)
  const [enviandoEstudio, setEnviandoEstudio] = useState(false)

  useEffect(() => {
    if (!aprobado || !idSolicitud) return
    obtenerOfertas(idSolicitud)
      .then(setOfertas)
      .catch(() =>
        setErrorOfertas(
          'No fue posible cargar las ofertas del backend; se muestra la estimación local.',
        ),
      )
  }, [aprobado, idSolicitud])

  const ofertaElegible = ofertas.find((o) => o.elegible)

  const cupoMaximo = ofertaElegible?.monto_aprobado
    ? Number(ofertaElegible.monto_aprobado)
    : resultado.montoSugerido
  const tasaOferta = ofertaElegible?.tasa_ofrecida
    ? Number(ofertaElegible.tasa_ofrecida)
    : resultado.tasaMensual

  const [plazo, setPlazo] = useState(resultado.plazoMeses)

  // Datos del vehículo a financiar (formalización). La marca se sugiere
  // según el concesionario del asesor de la cuenta.
  const [concesionario, setConcesionario] = useState(obtenerConcesionario)
  const [marca, setMarca] = useState(() =>
    marcaDeConcesionario(obtenerConcesionario()),
  )
  const [referencia, setReferencia] = useState('')
  const [modelo, setModelo] = useState<number | null>(null)
  const [color, setColor] = useState('')
  const [valorMoto, setValorMoto] = useState<number | null>(null)
  // El descuento es uno solo: en pesos O en porcentaje, nunca los dos.
  const [tipoDescuento, setTipoDescuento] = useState<'valor' | 'porcentaje'>(
    'valor',
  )
  const [descuento, setDescuento] = useState<number | null>(0)
  const [descuentoPct, setDescuentoPct] = useState<number | null>(0)
  const [accesorios, setAccesorios] = useState<number | null>(0)
  const [matricula, setMatricula] = useState<number | null>(0)
  const [soat, setSoat] = useState<number | null>(0)
  const [avalPct, setAvalPct] = useState<number | null>(0)

  useEffect(() => {
    if (ofertaElegible?.plazo_ofrecido) setPlazo(ofertaElegible.plazo_ofrecido)
  }, [ofertaElegible?.plazo_ofrecido])

  // Saldo a financiar = valor neto de la moto tras descuentos, más los
  // adicionales financiados (accesorios, matrícula, SOAT) y el aval.
  const descuentoAplicado =
    tipoDescuento === 'valor'
      ? (descuento ?? 0)
      : ((valorMoto ?? 0) * (descuentoPct ?? 0)) / 100
  const valorNeto = Math.max(0, (valorMoto ?? 0) - descuentoAplicado)
  const avalValor = (valorNeto * (avalPct ?? 0)) / 100
  const saldoFinanciar = Math.round(
    valorNeto + (accesorios ?? 0) + (matricula ?? 0) + (soat ?? 0) + avalValor,
  )
  const saldoInvalido = saldoFinanciar <= 0
  const superaCupo = cupoMaximo > 0 && saldoFinanciar > cupoMaximo

  const plazoInvalido = plazo < 12 || plazo > 48
  const cuotaMensual = useMemo(
    () =>
      plazoInvalido || saldoInvalido
        ? 0
        : Math.round(cuotaAnualidad(saldoFinanciar, tasaOferta, plazo)),
    [saldoFinanciar, plazo, tasaOferta, plazoInvalido, saldoInvalido],
  )
  const desembolsoEstimado = Math.round(saldoFinanciar * 0.99)
  // El cupo aprobado cuenta de 0 → valor para dar emoción al resultado.
  const cupoAnim = useCuentaAscendente(aprobado ? cupoMaximo : 0)

  const cambiarConcesionario = (nombre: string) => {
    setConcesionario(nombre)
    guardarConcesionario(nombre)
    setMarca(marcaDeConcesionario(nombre))
  }

  const formalizar = () => {
    if (plazoInvalido || saldoInvalido || superaCupo) return
    const oferta: OfertaSeleccionada = {
      monto: saldoFinanciar,
      plazoMeses: plazo,
      cuotaMensual,
      desembolsoEstimado,
      idOferta: ofertaElegible?.id_oferta,
    }
    if (!idSolicitud || !ofertaElegible) {
      onFormalizar(oferta)
      return
    }
    setConfirmando(true)
    seleccionarOferta(
      idSolicitud,
      ofertaElegible.id_oferta,
      saldoFinanciar,
      plazo,
      {
        marca: marca || null,
        referencia: referencia.trim() || null,
        modelo: modelo != null ? String(modelo) : null,
        color: color.trim() || null,
        valor_moto_iva: valorMoto,
        descuento: tipoDescuento === 'valor' ? descuento : null,
        descuento_pct: tipoDescuento === 'porcentaje' ? descuentoPct : null,
        accesorios,
        matricula,
        soat,
        aval_pct: avalPct,
      },
    )
      .then(() => {
        emitirToast({
          tipo: 'exito',
          titulo: 'Oferta confirmada',
          mensaje: 'La oferta y el vehículo quedaron registrados.',
        })
        onFormalizar(oferta)
      })
      .catch(() =>
        setErrorOfertas(
          'La oferta no pudo confirmarse en el backend; intenta de nuevo.',
        ),
      )
      .finally(() => setConfirmando(false))
  }

  // Escala el rechazo al comité: la solicitud queda 'en_revision' y la
  // resuelven con aprobar/rechazar manual en la bandeja del comité.
  const enviarEstudio = () => {
    if (!idSolicitud || enviandoEstudio || enEstudio) return
    setEnviandoEstudio(true)
    enviarAEstudio(idSolicitud)
      .then(() => {
        emitirToast({
          tipo: 'exito',
          titulo: 'Solicitud enviada a estudio',
          mensaje: 'El comité de crédito revisará la evaluación y decidirá.',
        })
        setEnEstudio(true)
        onEnviadaEstudio?.()
      })
      .catch(() =>
        emitirToast({
          tipo: 'error',
          titulo: 'No se pudo enviar a estudio',
          mensaje: 'Intenta de nuevo en unos segundos.',
        }),
      )
      .finally(() => setEnviandoEstudio(false))
  }

  const titulo = aprobado
    ? 'Oferta de crédito generada'
    : rechazado
      ? 'Solicitud rechazada'
      : 'Revisión manual requerida'
  const descripcion = aprobado
    ? 'Confirma los datos del vehículo y la financiación para continuar.'
    : rechazado
      ? 'La solicitud no cumple las políticas vigentes del motor de decisión.'
      : 'La solicitud requiere validación del comité antes de emitir una oferta.'

  return (
    <div className="resultado-credito">
      {!compacto && (
        <>
          <CabeceraEtapaOriginacion
            paso={5}
            titulo={titulo}
            descripcion={descripcion}
          />
          <SeguimientoOriginacion pasoActual={5} />
        </>
      )}

      <div
        className={`resultado-credito__veredicto resultado-credito__veredicto--${
          aprobado ? 'aprobado' : rechazadoVisible ? 'rechazado' : 'revision'
        }`}
        role="status"
      >
        {aprobado && (
          <div className="resultado-credito__confetti" aria-hidden="true">
            {CONFETTI.map((estilo, i) => (
              <i key={i} style={estilo} />
            ))}
          </div>
        )}
        <span className="resultado-credito__veredicto-icono" aria-hidden="true">
          {aprobado ? (
            <BadgeCheck size={42} strokeWidth={1.8} />
          ) : rechazadoVisible ? (
            <XCircle size={42} strokeWidth={1.8} />
          ) : (
            <Clock3 size={42} strokeWidth={1.8} />
          )}
        </span>
        <span className="resultado-credito__veredicto-eyebrow">
          {aprobado
            ? '¡Buenas noticias!'
            : rechazadoVisible
              ? 'Decisión del motor'
              : 'Decisión pendiente'}
        </span>
        <strong className="resultado-credito__veredicto-titulo">
          {aprobado
            ? '¡Crédito aprobado!'
            : rechazadoVisible
              ? 'Crédito no aprobado'
              : 'En revisión por el comité'}
        </strong>
        {aprobado ? (
          <span className="resultado-credito__veredicto-cupo">
            <small>Cupo aprobado hasta</small>
            <b>{currency(Math.round(cupoAnim))}</b>
          </span>
        ) : (
          <p className="resultado-credito__veredicto-sub">
            {rechazadoVisible
              ? enEstudio || revisionManual
                ? 'La solicitud quedó en revisión manual del comité de crédito.'
                : 'Puedes corregir los datos de la solicitud, o enviarla a estudio para revisión del comité.'
              : 'El comité de crédito revisará la evaluación antes de emitir una oferta.'}
          </p>
        )}
        <span className="resultado-credito__veredicto-pill">
          {aprobado
            ? 'Aprobado'
            : rechazadoVisible
              ? 'No aprobado'
              : 'Pendiente de comité'}
        </span>
        <small className="resultado-credito__veredicto-radicado">
          {idSolicitud
            ? `Solicitud ${idSolicitud.slice(0, 8).toUpperCase()}`
            : 'Evaluación de demostración'}
        </small>
      </div>

      {formalizacionIniciada && (
        <Alerta variante="exito">
          Formalización iniciada. Las condiciones quedan listas para validación
          documental y firma.
          {idSolicitud && (
            <>
              {' '}
              El siguiente paso es la firma del pagaré y la confirmación del
              desembolso en el detalle de la solicitud:{' '}
              <Link to={`/solicitudes/${idSolicitud}`}>
                Ir a formalización y desembolso
              </Link>
              .
            </>
          )}
        </Alerta>
      )}

      {errorOfertas && <Alerta variante="advertencia">{errorOfertas}</Alerta>}

      {aprobado ? (
        <div className="resultado-credito__contenido">
          <section className="resultado-credito__oferta">
            <header>
              <h2>Información de crédito</h2>
              <span>
                {resultado.esDemo
                  ? 'Aprobado viable · Demostración'
                  : `Aprobado · ${ofertaElegible ? 'Oferta real generada' : 'Evaluación real'}`}
              </span>
            </header>

            <div className="resultado-credito__cupo">
              <small>Cupo máximo aprobado</small>
              <strong>{currency(cupoMaximo)}</strong>
              <p>
                Cuota de referencia {currency(resultado.cuotaSugerida)} a{' '}
                {resultado.plazoMeses} meses, según la capacidad de pago
                evaluada por el motor.
              </p>
            </div>

            <div className="resultado-credito__seleccion">
              <div className="resultado-credito__seleccion-head">
                <strong>Detalles de la financiación</strong>
              </div>
              <div className="resultado-credito__grid">
                <label>
                  Concesionario
                  <select
                    className="input-base"
                    value={concesionario}
                    disabled={formalizacionIniciada || confirmando}
                    onChange={(e) => cambiarConcesionario(e.target.value)}
                  >
                    {CONCESIONARIOS.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                    {!CONCESIONARIOS.includes(concesionario) && (
                      <option value={concesionario}>{concesionario}</option>
                    )}
                  </select>
                </label>
                <label>
                  Marca
                  <select
                    className="input-base"
                    value={marca}
                    disabled={formalizacionIniciada || confirmando}
                    onChange={(e) => setMarca(e.target.value)}
                  >
                    {MARCAS_VEHICULO.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                    {!MARCAS_VEHICULO.includes(marca) && (
                      <option value={marca}>{marca}</option>
                    )}
                  </select>
                </label>
                <label>
                  Referencia
                  <input
                    className="input-base"
                    value={referencia}
                    disabled={formalizacionIniciada || confirmando}
                    placeholder="PULSAR NS 160FI UG"
                    onChange={(e) => setReferencia(e.target.value)}
                  />
                </label>
                <label>
                  Modelo (año)
                  <CampoNumerico
                    className="input-base"
                    value={modelo}
                    minimo={1990}
                    disabled={formalizacionIniciada || confirmando}
                    placeholder={String(new Date().getFullYear())}
                    onValor={(n) => setModelo(n)}
                  />
                </label>
                <label>
                  Color
                  <input
                    className="input-base"
                    value={color}
                    disabled={formalizacionIniciada || confirmando}
                    placeholder="NEGRO CRISTAL ONIX"
                    onChange={(e) => setColor(e.target.value)}
                  />
                </label>
                <label>
                  Valor moto + IVA
                  <CampoNumerico
                    className="input-base"
                    formatoMiles
                    minimo={0}
                    value={valorMoto}
                    disabled={formalizacionIniciada || confirmando}
                    placeholder="6.899.000"
                    onValor={(n) => setValorMoto(n)}
                  />
                </label>
                <div className="resultado-credito__descuento">
                  <span>
                    Descuento
                    <span
                      className="resultado-credito__toggle"
                      role="group"
                      aria-label="Tipo de descuento"
                    >
                      <button
                        type="button"
                        className={
                          tipoDescuento === 'valor'
                            ? 'resultado-credito__toggle-op resultado-credito__toggle-op--activo'
                            : 'resultado-credito__toggle-op'
                        }
                        disabled={formalizacionIniciada || confirmando}
                        onClick={() => setTipoDescuento('valor')}
                      >
                        $
                      </button>
                      <button
                        type="button"
                        className={
                          tipoDescuento === 'porcentaje'
                            ? 'resultado-credito__toggle-op resultado-credito__toggle-op--activo'
                            : 'resultado-credito__toggle-op'
                        }
                        disabled={formalizacionIniciada || confirmando}
                        onClick={() => setTipoDescuento('porcentaje')}
                      >
                        %
                      </button>
                    </span>
                  </span>
                  {tipoDescuento === 'valor' ? (
                    <CampoNumerico
                      className="input-base"
                      formatoMiles
                      minimo={0}
                      value={descuento}
                      disabled={formalizacionIniciada || confirmando}
                      aria-label="Descuento en pesos"
                      placeholder="0"
                      onValor={(n) => setDescuento(n)}
                    />
                  ) : (
                    <input
                      type="number"
                      className="input-base"
                      min={0}
                      max={100}
                      value={descuentoPct ?? ''}
                      disabled={formalizacionIniciada || confirmando}
                      aria-label="Descuento en porcentaje"
                      placeholder="0"
                      onChange={(e) =>
                        setDescuentoPct(
                          e.target.value === '' ? null : Number(e.target.value),
                        )
                      }
                    />
                  )}
                </div>
                <label>
                  Accesorios
                  <CampoNumerico
                    className="input-base"
                    formatoMiles
                    minimo={0}
                    value={accesorios}
                    disabled={formalizacionIniciada || confirmando}
                    placeholder="180.000"
                    onValor={(n) => setAccesorios(n)}
                  />
                </label>
                <label>
                  Matrícula
                  <CampoNumerico
                    className="input-base"
                    formatoMiles
                    minimo={0}
                    value={matricula}
                    disabled={formalizacionIniciada || confirmando}
                    placeholder="450.000"
                    onValor={(n) => setMatricula(n)}
                  />
                </label>
                <label>
                  SOAT
                  <CampoNumerico
                    className="input-base"
                    formatoMiles
                    minimo={0}
                    value={soat}
                    disabled={formalizacionIniciada || confirmando}
                    placeholder="368.300"
                    onValor={(n) => setSoat(n)}
                  />
                </label>
                <label>
                  Aval %
                  <input
                    type="number"
                    className="input-base"
                    min={0}
                    max={100}
                    value={avalPct ?? ''}
                    disabled={formalizacionIniciada || confirmando}
                    placeholder="0"
                    onChange={(e) =>
                      setAvalPct(
                        e.target.value === '' ? null : Number(e.target.value),
                      )
                    }
                  />
                </label>
                <div className="resultado-credito__plazo">
                  <label htmlFor="rc-plazo">Plazo</label>
                  <CampoNumerico
                    id="rc-plazo"
                    className="input-base"
                    value={plazo}
                    disabled={formalizacionIniciada || confirmando}
                    onValor={(n) => setPlazo(n ?? 0)}
                    aria-invalid={plazoInvalido}
                    aria-describedby="rc-plazo-ayuda"
                  />
                  <small id="rc-plazo-ayuda">meses · 12–48</small>
                </div>
              </div>
              {plazoInvalido && (
                <p className="resultado-credito__plazo-error" role="alert">
                  El plazo debe estar entre 12 y 48 meses.
                </p>
              )}
              {saldoInvalido && (
                <p className="resultado-credito__plazo-error" role="alert">
                  Ingresa el valor de la moto para calcular el saldo a
                  financiar.
                </p>
              )}
              {!saldoInvalido && superaCupo && (
                <p className="resultado-credito__plazo-error" role="alert">
                  El saldo a financiar supera el cupo aprobado (
                  {currency(cupoMaximo)}); ajusta el valor o los descuentos.
                </p>
              )}
            </div>

            <dl className="resultado-credito__valores">
              <div>
                <dt>Saldo a financiar</dt>
                <dd>{saldoInvalido ? '—' : currency(saldoFinanciar)}</dd>
              </div>
              <div>
                <dt>Cuota mensual estimada</dt>
                <dd>
                  {plazoInvalido || saldoInvalido
                    ? '—'
                    : currency(cuotaMensual)}
                </dd>
              </div>
              <div>
                <dt>Plazo seleccionado</dt>
                <dd>{plazoInvalido ? '—' : `${plazo} meses`}</dd>
              </div>
              <div>
                <dt>Desembolso estimado</dt>
                <dd>
                  {saldoInvalido
                    ? '—'
                    : `${currency(desembolsoEstimado)} (menos GMF)`}
                </dd>
              </div>
            </dl>

            <p className="resultado-credito__tasa">
              <CircleAlert size={15} aria-hidden="true" />
              Tasa {resultado.esDemo ? 'ilustrativa' : 'ofrecida'}:{' '}
              {tasaOferta.toFixed(2)}% M.V. sujeta a confirmación en pagaré
              final.
            </p>

            <div className="resultado-credito__condiciones">
              <strong>Condiciones obligatorias para desembolso</strong>
              <p>
                1. Firma digital del pagaré desmaterializado. 2. Verificación de
                una cuenta bancaria nacional de destino.
              </p>
            </div>
          </section>

          <aside className="resultado-credito__vehiculo">
            <h2>La moto del cliente</h2>
            <div className="resultado-credito__vehiculo-hero">
              <span
                className="resultado-credito__vehiculo-icono"
                aria-hidden="true"
              >
                <Bike size={30} strokeWidth={1.7} />
              </span>
              <div>
                <strong>
                  {[marca, referencia.trim()].filter(Boolean).join(' ') ||
                    'Financiamiento de vehículo'}
                </strong>
                <small>
                  {[modelo, color.trim()].filter(Boolean).join(' · ') ||
                    concesionario}
                </small>
              </div>
            </div>

            <dl className="resultado-credito__vehiculo-datos">
              <div>
                <dt>Valor moto + IVA</dt>
                <dd>{valorMoto ? currency(valorMoto) : '—'}</dd>
              </div>
              <div>
                <dt>Saldo a financiar</dt>
                <dd>{saldoInvalido ? '—' : currency(saldoFinanciar)}</dd>
              </div>
              <div>
                <dt>Cuota mensual estimada</dt>
                <dd>
                  {plazoInvalido || saldoInvalido
                    ? '—'
                    : currency(cuotaMensual)}
                </dd>
              </div>
              <div>
                <dt>Plazo</dt>
                <dd>{plazoInvalido ? '—' : `${plazo} meses`}</dd>
              </div>
              <div>
                <dt>Total estimado a pagar</dt>
                <dd>
                  {plazoInvalido || saldoInvalido
                    ? '—'
                    : currency(cuotaMensual * plazo)}
                </dd>
              </div>
            </dl>

            <p className="resultado-credito__inclusion">
              La moto se entrega en {concesionario}; la entrega se agenda tras
              la firma del pagaré y el desembolso.
            </p>
          </aside>
        </div>
      ) : rechazadoVisible ? (
        <>
          {(enEstudio || (esAsesor && revisionManual)) && (
            <Alerta variante="informacion" titulo="Solicitud en estudio">
              <p>
                El comité de crédito revisará la evaluación y decidirá si se
                aprueba con condiciones especiales.
              </p>
            </Alerta>
          )}
          {/* Las causales del rechazo son sensibles: solo administrador. */}
          {!esAsesor && (
            <Alerta variante="error" titulo="Detalle del motor (administrador)">
              {resultado.causales.length ? (
                <ul>
                  {resultado.causales.map((causal) => (
                    <li key={causal.codigo}>
                      <strong>{causal.codigo}</strong> — {causal.descripcion}
                    </li>
                  ))}
                </ul>
              ) : (
                <p>El motor no reportó causales específicas.</p>
              )}
              {resultado.advertencias.length > 0 && (
                <p>
                  <small>{resultado.advertencias.join(' ')}</small>
                </p>
              )}
              <small>Auditoría: {resultado.auditoria}</small>
            </Alerta>
          )}
        </>
      ) : (
        <Alerta
          variante="advertencia"
          titulo="Solicitud enviada a revisión manual"
        >
          <p>
            {resultado.decisionInterna === 'Requiere Codeudor'
              ? 'El motor sugiere aprobación condicionada a un codeudor; el comité debe resolver.'
              : 'No se ha generado una oferta aprobada. El comité debe resolver la evaluación pendiente.'}
          </p>
          {!esAsesor && resultado.causales.length > 0 && (
            <ul>
              {resultado.causales.map((causal) => (
                <li key={causal.codigo}>
                  <strong>{causal.codigo}</strong> — {causal.descripcion}
                </li>
              ))}
            </ul>
          )}
          <small>Auditoría: {resultado.auditoria}</small>
        </Alerta>
      )}

      <footer className="resultado-credito__acciones">
        <button
          className="resultado-credito__secundario"
          type="button"
          onClick={onModificar}
          disabled={formalizacionIniciada || confirmando || enviandoEstudio}
        >
          <ArrowLeft size={15} aria-hidden="true" />
          {rechazado ? 'Corregir datos de la solicitud' : 'Modificar oferta'}
        </button>
        {aprobado && (
          <button
            className="resultado-credito__primario"
            type="button"
            onClick={formalizar}
            disabled={
              formalizacionIniciada ||
              confirmando ||
              plazoInvalido ||
              saldoInvalido ||
              superaCupo
            }
          >
            {formalizacionIniciada
              ? 'Formalización iniciada'
              : confirmando
                ? 'Confirmando oferta…'
                : 'Continuar a formalización'}
            {!formalizacionIniciada && !confirmando && (
              <Check size={15} aria-hidden="true" />
            )}
          </button>
        )}
        {rechazado && idSolicitud && (
          <button
            className="resultado-credito__primario resultado-credito__primario--estudio"
            type="button"
            onClick={enviarEstudio}
            disabled={
              formalizacionIniciada ||
              confirmando ||
              enviandoEstudio ||
              enEstudio
            }
          >
            {enEstudio
              ? 'Enviada a estudio'
              : enviandoEstudio
                ? 'Enviando…'
                : 'Enviar a estudio'}
            {!enEstudio && !enviandoEstudio && (
              <FileSearch size={15} aria-hidden="true" />
            )}
          </button>
        )}
      </footer>
    </div>
  )
}

export default ResultadoCredito
