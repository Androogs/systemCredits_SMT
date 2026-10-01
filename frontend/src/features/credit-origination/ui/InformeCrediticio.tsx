import { ArrowLeft, ArrowRight, Info } from 'lucide-react'
import { currency } from '../../../shared/lib/formatters'
import SeguimientoOriginacion from './SeguimientoOriginacion/SeguimientoOriginacion'
import CabeceraEtapaOriginacion from './CabeceraEtapaOriginacion'
import './CabeceraEtapaOriginacion.css'
import './InformeCrediticio.css'

interface InformeCrediticioProps {
  onModificarDatos: () => void
  onContinue: () => void
}

const indicadores = [
  {
    etiqueta: 'Obligaciones abiertas',
    valor: '3 activas',
    detalle: `Saldo total vigente: ${currency(8_400_000)} en sector bancario.`,
  },
  {
    etiqueta: 'Comportamiento histórico',
    valor: '100% al día',
    detalle: 'Sin reportes negativos de mora en los últimos 48 meses.',
    tono: 'positivo',
  },
  {
    etiqueta: 'Utilización de rotativos',
    valor: '28% promedio',
    detalle: 'Uso saludable de cupos de tarjeta de crédito aprobados.',
  },
  {
    etiqueta: 'Consultas recientes',
    valor: '1 en los últimos 6 meses',
    detalle: 'Baja frecuencia de búsqueda de financiación paralela.',
  },
] as const

function InformeCrediticio({
  onModificarDatos,
  onContinue,
}: InformeCrediticioProps) {
  return (
    <div className="informe-crediticio">
      <CabeceraEtapaOriginacion
        paso={10}
        titulo="Historial Crediticio · Datacrédito consolidado"
        descripcion="Resumen de obligaciones, comportamiento de pago y score del solicitante."
      />

      <SeguimientoOriginacion pasoActual={10} />

      <div className="informe-crediticio__resumen">
        <section
          className="informe-crediticio__puntaje"
          aria-labelledby="informe-puntaje"
        >
          <span id="informe-puntaje">Puntaje crediticio</span>
          <div className="informe-crediticio__puntaje-valor">
            <strong>742</strong>
            <span>Riesgo bajo</span>
          </div>
          <small>
            Rango del modelo: 150 a 950 puntos. Datos demostrativos.
          </small>
        </section>

        <aside className="informe-crediticio__politica" role="note">
          <h2>
            <Info size={16} aria-hidden="true" />
            Política de evaluación responsable
          </h2>
          <p>
            El score es un indicador sintético de patrones pasados, pero no
            constituye por sí solo una decisión de aprobación o rechazo. La
            decisión final requiere evaluar capacidad de pago, políticas
            integrales y revisión de documentos.
          </p>
        </aside>
      </div>

      <section
        className="informe-crediticio__obligaciones"
        aria-labelledby="informe-obligaciones"
      >
        <h2 id="informe-obligaciones">Análisis detallado de obligaciones</h2>
        <div className="informe-crediticio__indicadores">
          {indicadores.map((indicador) => (
            <article
              className={`informe-crediticio__indicador${'tono' in indicador ? ' is-positive' : ''}`}
              key={indicador.etiqueta}
            >
              <span>{indicador.etiqueta}</span>
              <strong>{indicador.valor}</strong>
              <small>{indicador.detalle}</small>
            </article>
          ))}
          <article className="informe-crediticio__indicador informe-crediticio__indicador--wide">
            <span>Por definir</span>
            <strong>Información pendiente</strong>
            <small>
              Se completará cuando el proveedor entregue el informe real.
            </small>
          </article>
        </div>
      </section>

      <footer className="informe-crediticio__acciones">
        <button
          className="informe-crediticio__secundario"
          type="button"
          onClick={onModificarDatos}
        >
          <ArrowLeft size={15} aria-hidden="true" />
          Modificar datos
        </button>
        <button
          className="informe-crediticio__primario"
          type="button"
          onClick={onContinue}
        >
          Proceder a evaluación integral
          <ArrowRight size={15} aria-hidden="true" />
        </button>
      </footer>
    </div>
  )
}

export default InformeCrediticio
