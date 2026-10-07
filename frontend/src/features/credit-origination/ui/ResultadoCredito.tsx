import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Check, CircleAlert } from 'lucide-react'
import { currency } from '../../../shared/lib/formatters'
import { cuotaAnualidad } from '../../../shared/lib/finanzas'
import Alerta from '../../../shared/ui/Alerta'
import type { ResultadoEvaluacionCredito } from '../model/resultado-evaluacion'
import {
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
}

const MONTO_MINIMO = 500_000
const PASO_MONTO = 50_000
const plazosDisponibles = [12, 24, 36, 48]

function ResultadoCredito({
  resultado,
  idSolicitud,
  formalizacionIniciada,
  onModificar,
  onFormalizar,
}: ResultadoCreditoProps) {
  const aprobado = resultado.decision === 'APROBADO'
  const rechazado = resultado.decision === 'RECHAZADO'

  const [ofertas, setOfertas] = useState<OfertaApi[]>([])
  const [errorOfertas, setErrorOfertas] = useState<string | null>(null)
  const [confirmando, setConfirmando] = useState(false)

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

  const [montoTomar, setMontoTomar] = useState(resultado.montoSugerido)
  const [plazo, setPlazo] = useState(resultado.plazoMeses)

  useEffect(() => {
    if (cupoMaximo > 0 && montoTomar > cupoMaximo) setMontoTomar(cupoMaximo)
    if (ofertaElegible?.plazo_ofrecido) setPlazo(ofertaElegible.plazo_ofrecido)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cupoMaximo, ofertaElegible?.plazo_ofrecido])

  const cuotaMensual = useMemo(
    () => Math.round(cuotaAnualidad(montoTomar, tasaOferta, plazo)),
    [montoTomar, plazo, tasaOferta],
  )
  const desembolsoEstimado = Math.round(montoTomar * 0.99)

  const formalizar = () => {
    const oferta: OfertaSeleccionada = {
      monto: montoTomar,
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
    seleccionarOferta(idSolicitud, ofertaElegible.id_oferta, montoTomar, plazo)
      .then(() => onFormalizar(oferta))
      .catch(() =>
        setErrorOfertas(
          'La oferta no pudo confirmarse en el backend; intenta de nuevo.',
        ),
      )
      .finally(() => setConfirmando(false))
  }

  const titulo = aprobado
    ? 'Oferta de crédito generada'
    : rechazado
      ? 'Solicitud rechazada'
      : 'Revisión manual requerida'
  const descripcion = aprobado
    ? 'El sistema sugiere un cupo según la capacidad del cliente; confirma cuánto desea tomar.'
    : rechazado
      ? 'La solicitud no cumple las políticas vigentes del motor de decisión.'
      : 'La solicitud requiere validación del comité antes de emitir una oferta.'

  return (
    <div className="resultado-credito">
      <CabeceraEtapaOriginacion
        paso={12}
        titulo={titulo}
        descripcion={descripcion}
      />

      <SeguimientoOriginacion pasoActual={12} />

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
              <h2>1. Cupo sugerido por el sistema</h2>
              <span>
                {resultado.esDemo
                  ? 'Aprobado viable · Demostración'
                  : `Aprobado · ${ofertaElegible ? 'Oferta real generada' : 'Evaluación real'}`}
              </span>
            </header>

            <div className="resultado-credito__cupo">
              <small>Cupo máximo sugerido</small>
              <strong>{currency(cupoMaximo)}</strong>
              <p>
                Cuota de referencia {currency(resultado.cuotaSugerida)} a{' '}
                {resultado.plazoMeses} meses, según la capacidad de pago
                evaluada por el motor.
              </p>
            </div>

            <div className="resultado-credito__seleccion">
              <div className="resultado-credito__seleccion-head">
                <strong>2. ¿Cuánto desea tomar el cliente?</strong>
                <span>{currency(montoTomar)}</span>
              </div>
              <input
                className="resultado-credito__rango"
                type="range"
                min={Math.min(MONTO_MINIMO, cupoMaximo)}
                max={cupoMaximo}
                step={PASO_MONTO}
                value={montoTomar}
                aria-label="Monto a tomar del cupo sugerido"
                disabled={formalizacionIniciada || confirmando}
                onChange={(e) => setMontoTomar(Number(e.target.value))}
              />
              <div className="resultado-credito__rango-extremos">
                <span>{currency(MONTO_MINIMO)}</span>
                <span>{currency(cupoMaximo)}</span>
              </div>

              <label className="resultado-credito__plazo">
                Plazo
                <select
                  value={plazo}
                  disabled={formalizacionIniciada || confirmando}
                  onChange={(e) => setPlazo(Number(e.target.value))}
                >
                  {plazosDisponibles.map((meses) => (
                    <option key={meses} value={meses}>
                      {meses} meses
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <dl className="resultado-credito__valores">
              <div>
                <dt>Monto a tomar</dt>
                <dd>{currency(montoTomar)}</dd>
              </div>
              <div>
                <dt>Cuota mensual estimada</dt>
                <dd>{currency(cuotaMensual)}</dd>
              </div>
              <div>
                <dt>Plazo seleccionado</dt>
                <dd>{plazo} meses</dd>
              </div>
              <div>
                <dt>Desembolso estimado</dt>
                <dd>{currency(desembolsoEstimado)} (menos GMF)</dd>
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

          <aside className="resultado-credito__estados">
            <h2>Estados no viables / manuales</h2>
            <div className="resultado-credito__estado resultado-credito__estado--rechazo">
              <strong>En caso de rechazo</strong>
              <p>
                Se detallará el motivo de política no cumplida de forma
                explicable y sin sesgos.
              </p>
            </div>
            <div className="resultado-credito__estado resultado-credito__estado--revision">
              <strong>En caso de revisión manual</strong>
              <p>
                El comité de crédito analizará excepciones de ingresos no
                estándar.
              </p>
            </div>
            <p className="resultado-credito__inclusion">
              Las decisiones deben respetar las directrices de inclusión
              financiera y no discriminación.
            </p>
          </aside>
        </div>
      ) : rechazado ? (
        <Alerta variante="error" titulo="Solicitud rechazada por política">
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
          {resultado.causales.length > 0 && (
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
          disabled={formalizacionIniciada || confirmando}
        >
          <ArrowLeft size={15} aria-hidden="true" />
          Modificar oferta
        </button>
        {aprobado && (
          <button
            className="resultado-credito__primario"
            type="button"
            onClick={formalizar}
            disabled={formalizacionIniciada || confirmando}
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
      </footer>
    </div>
  )
}

export default ResultadoCredito
