import { ArrowLeft, ArrowRight, CircleAlert, CircleCheck } from 'lucide-react'
import { currency } from '../../../shared/lib/formatters'
import type { DatosSolicitud } from './CrearSolicitud'
import {
  calcularCupoSugerido,
  crearResultadoDemo,
  type ResultadoEvaluacionCredito,
} from '../model/resultado-evaluacion'
import SeguimientoOriginacion from './SeguimientoOriginacion/SeguimientoOriginacion'
import CabeceraEtapaOriginacion from './CabeceraEtapaOriginacion'
import './CabeceraEtapaOriginacion.css'
import './EvaluacionIntegral.css'

interface EvaluacionIntegralProps {
  solicitud?: DatosSolicitud
  /** Resultado ya obtenido del motor en el paso 9 (consulta). */
  resultadoPrevio?: ResultadoEvaluacionCredito
  onBack: () => void
  onRevisionManual: (resultado: ResultadoEvaluacionCredito) => void
  onContinue: (resultado: ResultadoEvaluacionCredito) => void
}

function EvaluacionIntegral({
  solicitud,
  resultadoPrevio,
  onBack,
  onRevisionManual,
  onContinue,
}: EvaluacionIntegralProps) {
  const ingresos = solicitud?.ingresosMensuales ?? 0
  const egresos = solicitud?.egresosMensuales ?? 0
  const plazoMeses = solicitud?.plazoMeses ?? 36
  const capacidadDisponible = Math.max(0, ingresos - egresos)
  const cupoSugerido =
    resultadoPrevio?.montoSugerido ??
    calcularCupoSugerido(ingresos, egresos, plazoMeses).monto

  const factors = resultadoPrevio?.trazabilidad.length
    ? resultadoPrevio.trazabilidad.map((paso) => ({
        titulo: paso.etapa.replaceAll('_', ' '),
        detalle: paso.detalle.join(' · ') || paso.resultado,
        resultado: paso.resultado === 'Sin causales' ? 'cumple' : 'pendiente',
      }))
    : ([
        {
          titulo: 'Capacidad de endeudamiento apta',
          detalle: `${currency(ingresos)} en ingresos y ${currency(egresos)} en egresos declarados; disponible estimado ${currency(capacidadDisponible)}.`,
          resultado: 'cumple',
        },
        {
          titulo: 'Verificación laboral telefónica pendiente',
          detalle:
            'Requiere confirmar con el departamento de RR. HH. de la empresa contratante.',
          resultado: 'pendiente',
        },
      ] as const)

  const resultadoEfectivo =
    resultadoPrevio ??
    crearResultadoDemo({
      decision: 'APROBADO',
      ingresosMensuales: ingresos,
      egresosMensuales: egresos,
      plazoMeses,
    })

  return (
    <div className="evaluacion-integral">
      <CabeceraEtapaOriginacion
        paso={11}
        titulo="Evaluación de políticas de riesgo"
        descripcion={
          resultadoPrevio && !resultadoPrevio.esDemo
            ? `Resultado del motor de decisión: ${resultadoPrevio.decisionInterna ?? resultadoPrevio.decision}.`
            : 'Integración del comportamiento del cliente, perfil socioeconómico y límites del motor de reglas interno.'
        }
      />

      <SeguimientoOriginacion pasoActual={11} />

      <div className="evaluacion-integral__contenido">
        <section
          className="evaluacion-integral__factores"
          aria-labelledby="evaluacion-factores"
        >
          <h2 id="evaluacion-factores">
            {resultadoPrevio?.trazabilidad.length
              ? 'Trazabilidad del motor de decisión'
              : 'Factores analizados por el sistema'}
          </h2>
          <ul>
            {factors.map((factor) => (
              <li key={factor.titulo}>
                <span
                  className={`evaluacion-integral__icono evaluacion-integral__icono--${factor.resultado}`}
                  aria-hidden="true"
                >
                  {factor.resultado === 'cumple' ? (
                    <CircleCheck size={17} />
                  ) : (
                    <CircleAlert size={17} />
                  )}
                </span>
                <div>
                  <strong>{factor.titulo}</strong>
                  <p>{factor.detalle}</p>
                </div>
              </li>
            ))}
          </ul>
          {resultadoPrevio?.causales.length ? (
            <ul className="evaluacion-integral__causales">
              {resultadoPrevio.causales.map((causal) => (
                <li key={causal.codigo}>
                  <strong>{causal.codigo}</strong> — {causal.descripcion}
                </li>
              ))}
            </ul>
          ) : null}
          <p className="evaluacion-integral__auditoria">
            ID de auditoría del motor de reglas:{' '}
            <strong>{resultadoEfectivo.auditoria}</strong> · Versión de
            políticas: <strong>{resultadoEfectivo.versionPolitica}</strong>
            {resultadoPrevio?.scoreConsultado != null && (
              <>
                {' '}
                · Score: <strong>{resultadoPrevio.scoreConsultado}</strong>
              </>
            )}
          </p>
        </section>

        <aside className="evaluacion-integral__recomendacion">
          <span>Recomendación financiera</span>
          <small>Capacidad disponible declarada</small>
          <strong className="evaluacion-integral__monto">
            {currency(capacidadDisponible)}
          </strong>
          {resultadoPrevio &&
          !resultadoPrevio.esDemo &&
          resultadoPrevio.decision !== 'APROBADO' ? (
            <div>
              <small>Cupo sugerido por el motor</small>
              <strong>
                {resultadoPrevio.decision === 'RECHAZADO'
                  ? 'No aplica — solicitud rechazada'
                  : 'Pendiente — requiere comité'}
              </strong>
            </div>
          ) : (
            <div>
              <small>Cupo máximo sugerido por el motor</small>
              <strong>{currency(cupoSugerido)}</strong>
            </div>
          )}
          <p>
            {resultadoPrevio &&
            !resultadoPrevio.esDemo &&
            resultadoPrevio.decision !== 'APROBADO'
              ? 'Las causales del motor se detallan en la trazabilidad; la pantalla final muestra el motivo.'
              : `A ${plazoMeses} meses según capacidad de pago · El cliente decide cuánto de este cupo toma en la oferta final.`}
          </p>
        </aside>
      </div>

      <footer className="evaluacion-integral__acciones">
        <button
          className="evaluacion-integral__secundario"
          type="button"
          onClick={onBack}
        >
          <ArrowLeft size={15} aria-hidden="true" />
          Volver al informe
        </button>
        <button
          className="evaluacion-integral__revision"
          type="button"
          onClick={() =>
            onRevisionManual({
              ...resultadoEfectivo,
              decision: 'REVISION_MANUAL',
            })
          }
        >
          Enviar a revisión manual
        </button>
        <button
          className="evaluacion-integral__primario"
          type="button"
          onClick={() => onContinue(resultadoEfectivo)}
        >
          Confirmar y generar resultado
          <ArrowRight size={15} aria-hidden="true" />
        </button>
      </footer>
    </div>
  )
}

export default EvaluacionIntegral
