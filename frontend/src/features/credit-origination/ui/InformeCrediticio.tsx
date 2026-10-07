import { ArrowLeft, ArrowRight, Info } from 'lucide-react'
import { currency } from '../../../shared/lib/formatters'
import type { ResultadoEvaluacionCredito } from '../model/resultado-evaluacion'
import SeguimientoOriginacion from './SeguimientoOriginacion/SeguimientoOriginacion'
import CabeceraEtapaOriginacion from './CabeceraEtapaOriginacion'
import './CabeceraEtapaOriginacion.css'
import './InformeCrediticio.css'

interface InformeCrediticioProps {
  onModificarDatos: () => void
  onContinue: () => void
  /** Resultado real del motor (paso 9). Sin él se muestran datos demo. */
  resultado?: ResultadoEvaluacionCredito
}

interface Indicador {
  etiqueta: string
  valor: string
  detalle: string
  tono?: 'positivo' | 'alerta'
  anchoCompleto?: boolean
}

const indicadoresDemo: Indicador[] = [
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
]

const ETIQUETA_PERFIL_SCORE: Record<string, string> = {
  A: 'Riesgo bajo',
  B: 'Riesgo moderado',
  C: 'Riesgo alto',
  D: 'Riesgo muy alto',
}

/** Etiqueta de riesgo derivada del puntaje cuando el motor no asigna perfil. */
function riesgoDesdeScore(score: number): string {
  if (score >= 750) return 'Riesgo bajo'
  if (score >= 650) return 'Riesgo moderado'
  if (score >= 500) return 'Riesgo alto'
  return 'Riesgo muy alto'
}

function numero(valor: unknown): number {
  const n = Number(valor)
  return Number.isFinite(n) ? n : 0
}

/** Traduce los indicadores_buro del motor a tarjetas legibles. */
function indicadoresDesdeMotor(
  resultado: ResultadoEvaluacionCredito,
): Indicador[] {
  const buro = resultado.indicadoresBuro ?? {}
  const lista: Indicador[] = []

  const alertas = [
    ['embargos', 'embargo'],
    ['cancelaciones_mal_manejo', 'cancelación por mal manejo'],
    ['cartera_castigada', 'cartera castigada'],
    ['dudoso_recaudo', 'dudoso recaudo'],
    ['calificaciones_negativas', 'calificación negativa'],
    ['reestructuraciones', 'reestructuración'],
  ] as const
  const activas = alertas
    .map(([clave, etiqueta]) => ({
      clave,
      etiqueta,
      cantidad: numero(buro[clave]),
    }))
    .filter((a) => a.cantidad > 0)
  lista.push({
    etiqueta: 'Alertas del buró',
    valor:
      activas.length === 0
        ? 'Sin alertas vigentes'
        : `${activas.reduce((t, a) => t + a.cantidad, 0)} reportadas`,
    detalle:
      activas.length === 0
        ? 'Sin embargos, cancelaciones, cartera castigada ni reestructuraciones.'
        : activas
            .map(
              (a) => `${a.cantidad} ${a.etiqueta}${a.cantidad > 1 ? 'es' : ''}`,
            )
            .join(' · '),
    tono: activas.length === 0 ? 'positivo' : 'alerta',
  })

  const morasVigentes =
    numero(buro.mora_30_vigente) + numero(buro.mora_60_vigente)
  const morasHistoricas =
    numero(buro.moras_30_historicas) +
    numero(buro.moras_60_historicas) +
    numero(buro.moras_90_historicas)
  lista.push({
    etiqueta: 'Comportamiento de pago',
    valor:
      morasVigentes === 0
        ? 'Sin moras vigentes'
        : `${morasVigentes} obligación${morasVigentes > 1 ? 'es' : ''} en mora`,
    detalle:
      morasHistoricas === 0
        ? 'Sin moras históricas de 30/60/90 días reportadas.'
        : `${morasHistoricas} mora${morasHistoricas > 1 ? 's' : ''} histórica${morasHistoricas > 1 ? 's' : ''} (30/60/90 días).`,
    tono: morasVigentes === 0 ? 'positivo' : 'alerta',
  })

  if (resultado.endeudamiento !== undefined) {
    lista.push({
      etiqueta: 'Endeudamiento actual',
      valor: `${resultado.endeudamiento.toFixed(2)}%`,
      detalle:
        resultado.disponible !== undefined
          ? `Disponible mensual tras gastos: ${currency(resultado.disponible)}.`
          : 'Relación obligaciones financieras / ingreso evaluado.',
      tono:
        resultado.endeudamiento <= 75
          ? 'positivo'
          : resultado.endeudamiento <= 90
            ? undefined
            : 'alerta',
    })
  }

  if (resultado.capacidadPago !== undefined) {
    lista.push({
      etiqueta: 'Capacidad de pago',
      valor: currency(resultado.capacidadPago),
      detalle:
        resultado.ingresoFinal !== undefined
          ? `Ingreso final depurado: ${currency(resultado.ingresoFinal)}` +
            (resultado.fuenteIngreso
              ? ` (fuente: ${resultado.fuenteIngreso.replaceAll('_', ' ')})`
              : '') +
            (resultado.ingresoFinalSmmlv !== undefined
              ? ` · ${resultado.ingresoFinalSmmlv.toFixed(2)} SMMLV`
              : '')
          : 'Capacidad mensual estimada para cuota de crédito.',
      tono: resultado.capacidadPago > 0 ? 'positivo' : 'alerta',
    })
  }

  lista.push({
    etiqueta: 'Documento de identidad',
    valor:
      buro.documento_vigente === false ? 'No vigente / en trámite' : 'Vigente',
    detalle:
      buro.reportado_fallecido === true
        ? 'ALERTA: el buró reporta al titular como fallecido.'
        : `Estado en buró: ${String(buro.estado_documento ?? '00')}${
            buro.peor_calificacion
              ? ` · peor calificación ${String(buro.peor_calificacion)}`
              : ''
          }.`,
    tono:
      buro.documento_vigente === false || buro.reportado_fallecido === true
        ? 'alerta'
        : 'positivo',
  })

  if (resultado.perfilScore || resultado.perfilIngreso) {
    lista.push({
      etiqueta: 'Perfil del motor',
      valor: [
        resultado.perfilScore ? `Score ${resultado.perfilScore}` : null,
        resultado.perfilIngreso ? `Ingreso ${resultado.perfilIngreso}` : null,
      ]
        .filter(Boolean)
        .join(' · '),
      detalle: 'Clasificación que alimenta la matriz de decisión.',
      anchoCompleto: true,
    })
  }

  return lista
}

function InformeCrediticio({
  onModificarDatos,
  onContinue,
  resultado,
}: InformeCrediticioProps) {
  const esReal = Boolean(resultado && !resultado.esDemo)
  const indicadores = esReal
    ? indicadoresDesdeMotor(resultado!)
    : indicadoresDemo

  const puntaje = resultado?.scoreConsultado ?? 742
  const etiquetaPuntaje = resultado?.perfilScore
    ? (ETIQUETA_PERFIL_SCORE[resultado.perfilScore] ??
      `Perfil ${resultado.perfilScore}`)
    : esReal
      ? riesgoDesdeScore(puntaje)
      : 'Riesgo bajo'
  const puntajeAdverso =
    esReal &&
    (resultado!.decision === 'RECHAZADO' ||
      resultado!.decision === 'REVISION_MANUAL')

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
          <div
            className={`informe-crediticio__puntaje-valor${puntajeAdverso ? ' is-alerta' : ''}`}
          >
            <strong>{puntaje}</strong>
            <span>{etiquetaPuntaje}</span>
          </div>
          <small>
            {esReal
              ? `Modelo consultado: ${resultado?.scoreTipo ?? 'HDC+'} · Datos del motor integrado.`
              : 'Rango del modelo: 150 a 950 puntos. Datos demostrativos.'}
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
              className={[
                'informe-crediticio__indicador',
                indicador.tono === 'positivo' ? 'is-positive' : '',
                indicador.tono === 'alerta' ? 'is-alerta' : '',
                indicador.anchoCompleto
                  ? 'informe-crediticio__indicador--wide'
                  : '',
              ]
                .filter(Boolean)
                .join(' ')}
              key={indicador.etiqueta}
            >
              <span>{indicador.etiqueta}</span>
              <strong>{indicador.valor}</strong>
              <small>{indicador.detalle}</small>
            </article>
          ))}
          {!esReal && (
            <article className="informe-crediticio__indicador informe-crediticio__indicador--wide">
              <span>Por definir</span>
              <strong>Información pendiente</strong>
              <small>
                Se completará cuando el proveedor entregue el informe real.
              </small>
            </article>
          )}
          {esReal && resultado!.advertencias.length > 0 && (
            <article className="informe-crediticio__indicador informe-crediticio__indicador--wide">
              <span>Advertencias del motor</span>
              <strong>{resultado!.advertencias.length} nota(s)</strong>
              <small>{resultado!.advertencias.join(' ')}</small>
            </article>
          )}
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
