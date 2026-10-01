import { ArrowLeft, Check, CircleAlert } from 'lucide-react'
import { currency } from '../../../shared/lib/formatters'
import Alerta from '../../../shared/ui/Alerta'
import type { ResultadoEvaluacionCreditoDemo } from '../model/resultado-evaluacion-demo'
import SeguimientoOriginacion from './SeguimientoOriginacion/SeguimientoOriginacion'
import CabeceraEtapaOriginacion from './CabeceraEtapaOriginacion'
import './CabeceraEtapaOriginacion.css'
import './ResultadoCredito.css'

interface ResultadoCreditoProps {
  resultado: ResultadoEvaluacionCreditoDemo
  formalizacionIniciada: boolean
  onModificar: () => void
  onFormalizar: () => void
}

function ResultadoCredito({
  resultado,
  formalizacionIniciada,
  onModificar,
  onFormalizar,
}: ResultadoCreditoProps) {
  const aprobado = resultado.decision === 'APROBADO'

  return (
    <div className="resultado-credito">
      <CabeceraEtapaOriginacion
        paso={12}
        titulo={
          aprobado ? 'Oferta de crédito generada' : 'Revisión manual requerida'
        }
        descripcion={
          aprobado
            ? 'Presenta al cliente las condiciones formales estructuradas para el desembolso del crédito.'
            : 'La solicitud requiere validación del comité antes de emitir una oferta.'
        }
      />

      <SeguimientoOriginacion pasoActual={12} />

      {formalizacionIniciada && (
        <Alerta variante="exito">
          Formalización iniciada. Las condiciones quedan listas para validación
          documental y firma.
        </Alerta>
      )}

      {aprobado ? (
        <div className="resultado-credito__contenido">
          <section className="resultado-credito__oferta">
            <header>
              <h2>1. Plan de pago aprobado</h2>
              <span>Aprobado viable · Demostración</span>
            </header>

            <dl className="resultado-credito__valores">
              <div>
                <dt>Monto total aprobado</dt>
                <dd>{currency(resultado.montoAprobado)}</dd>
              </div>
              <div>
                <dt>Monto estimado de desembolso</dt>
                <dd>{currency(resultado.desembolsoEstimado)} (menos GMF)</dd>
              </div>
              <div>
                <dt>Plazo confirmado</dt>
                <dd>{resultado.plazoMeses} meses</dd>
              </div>
              <div>
                <dt>Cuota mensual estimada</dt>
                <dd>{currency(resultado.cuotaMensual)}</dd>
              </div>
            </dl>

            <p className="resultado-credito__tasa">
              <CircleAlert size={15} aria-hidden="true" />
              Tasa ilustrativa aplicada: {resultado.tasaMensual.toFixed(2)}%
              M.V. sujeta a confirmación en pagaré final.
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
      ) : (
        <Alerta
          variante="advertencia"
          titulo="Solicitud enviada a revisión manual"
        >
          <p>
            No se ha generado una oferta aprobada. El comité debe resolver la
            verificación laboral pendiente antes de continuar.
          </p>
          <small>Auditoría: {resultado.auditoria}</small>
        </Alerta>
      )}

      <footer className="resultado-credito__acciones">
        <button
          className="resultado-credito__secundario"
          type="button"
          onClick={onModificar}
          disabled={formalizacionIniciada}
        >
          <ArrowLeft size={15} aria-hidden="true" />
          Modificar oferta
        </button>
        {aprobado && (
          <button
            className="resultado-credito__primario"
            type="button"
            onClick={onFormalizar}
            disabled={formalizacionIniciada}
          >
            {formalizacionIniciada
              ? 'Formalización iniciada'
              : 'Continuar a formalización'}
            {!formalizacionIniciada && <Check size={15} aria-hidden="true" />}
          </button>
        )}
      </footer>
    </div>
  )
}

export default ResultadoCredito
