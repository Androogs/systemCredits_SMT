import { ArrowLeft, ArrowRight, CircleAlert, CircleCheck } from 'lucide-react'
import { currency } from '../../../shared/lib/formatters'
import type { DatosSolicitud } from './CrearSolicitud'
import {
  crearResultadoEvaluacionCreditoDemo,
  type ResultadoEvaluacionCreditoDemo,
} from '../model/resultado-evaluacion-demo'
import SeguimientoOriginacion from './SeguimientoOriginacion/SeguimientoOriginacion'
import CabeceraEtapaOriginacion from './CabeceraEtapaOriginacion'
import './CabeceraEtapaOriginacion.css'
import './EvaluacionIntegral.css'

interface EvaluacionIntegralProps {
  solicitud?: DatosSolicitud
  onBack: () => void
  onRevisionManual: (resultado: ResultadoEvaluacionCreditoDemo) => void
  onContinue: (resultado: ResultadoEvaluacionCreditoDemo) => void
}

function EvaluacionIntegral({
  solicitud,
  onBack,
  onRevisionManual,
  onContinue,
}: EvaluacionIntegralProps) {
  const ingresos = solicitud?.ingresosMensuales ?? 4_500_000
  const egresos = solicitud?.egresosMensuales ?? 1_800_000
  const montoSolicitado = solicitud?.montoSolicitado ?? 15_000_000
  const plazoMeses = solicitud?.plazoMeses ?? 36
  const capacidadDisponible = Math.max(0, ingresos - egresos)
  const factors = [
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
  ] as const

  const generarResultado = (
    decision: ResultadoEvaluacionCreditoDemo['decision'],
  ) =>
    crearResultadoEvaluacionCreditoDemo({
      decision,
      montoSolicitado,
      plazoMeses,
    })

  return (
    <div className="evaluacion-integral">
      <CabeceraEtapaOriginacion
        paso={11}
        titulo="Evaluación de políticas de riesgo"
        descripcion="Integración del comportamiento del cliente, perfil socioeconómico y límites del motor de reglas interno."
      />

      <SeguimientoOriginacion pasoActual={11} />

      <div className="evaluacion-integral__contenido">
        <section
          className="evaluacion-integral__factores"
          aria-labelledby="evaluacion-factores"
        >
          <h2 id="evaluacion-factores">Factores analizados por el sistema</h2>
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
          <p className="evaluacion-integral__auditoria">
            ID de auditoría del motor de reglas: <strong>RULE-EVAL-4481</strong>{' '}
            · Versión de políticas: <strong>v2026.1</strong>
          </p>
        </section>

        <aside className="evaluacion-integral__recomendacion">
          <span>Recomendación financiera</span>
          <small>Monto original solicitado</small>
          <strong className="evaluacion-integral__monto">
            {currency(montoSolicitado)}
          </strong>
          <div>
            <small>Monto máximo sugerido por el motor</small>
            <strong>{currency(18_500_000)}</strong>
          </div>
          <p>
            Solicitud a {plazoMeses} meses · Valores demostrativos pendientes de
            evaluación real del motor.
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
          onClick={() => onRevisionManual(generarResultado('REVISION_MANUAL'))}
        >
          Enviar a revisión manual
        </button>
        <button
          className="evaluacion-integral__primario"
          type="button"
          onClick={() => onContinue(generarResultado('APROBADO'))}
        >
          Confirmar y generar resultado
          <ArrowRight size={15} aria-hidden="true" />
        </button>
      </footer>
    </div>
  )
}

export default EvaluacionIntegral
