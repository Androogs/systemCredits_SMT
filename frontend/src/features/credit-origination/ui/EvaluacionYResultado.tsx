import { useEffect, useState } from 'react'
import {
  ArrowLeft,
  ArrowRight,
  LoaderCircle,
  AlertTriangle,
} from 'lucide-react'
import Boton from '../../../shared/ui/Boton'
import {
  ApiError,
  evaluarSolicitud,
  listarAuditoriaSolicitud,
  listarEscenariosMock,
  obtenerAuditoria,
} from '../api/originacionApi'
import {
  construirEvaluacionPayload,
  primerApellido,
  type IdentidadSolicitante,
} from '../model/mapeos-api'
import {
  crearResultadoDemo,
  resultadoDesdeApi,
  type ResultadoEvaluacionCredito,
} from '../model/resultado-evaluacion'
import SeguimientoOriginacion from './SeguimientoOriginacion/SeguimientoOriginacion'
import ResultadoCredito, { type OfertaSeleccionada } from './ResultadoCredito'
import type { DatosSolicitud } from './CrearSolicitud'
import type { SimulacionPrevia } from '../model/borrador'
import './EvaluacionYResultado.css'

export interface DatosEvaluacion {
  origen: 'demo' | 'experian'
  escenarioMock: string
}

interface EvaluacionYResultadoProps {
  idSolicitud?: string
  solicitud?: DatosSolicitud
  identidad?: IdentidadSolicitante
  validacion?: { multasPendientes?: boolean }
  /** Resultado ya emitido (borrador retomado): se muestra sin re-evaluar. */
  resultadoInicial?: ResultadoEvaluacionCredito | null
  /** Simulación con la que se abrió la solicitud: precarga la formalización. */
  simulacion?: SimulacionPrevia
  onBack?: () => void
  onModificar: () => void
  /** Avisa al flujo que el motor ya entregó un resultado persistido. */
  onResultado?: (resultado: ResultadoEvaluacionCredito) => void
  /** Avisa al flujo que el proceso se cerró (oferta formalizada). */
  onFormalizar?: (oferta: OfertaSeleccionada) => void
}

const ESCENARIOS_POR_DEFECTO: Record<string, string> = {
  aprobado: 'Perfil aprobado',
  embargo: 'Con embargo vigente',
}

export default function EvaluacionYResultado({
  idSolicitud,
  solicitud,
  identidad,
  validacion,
  resultadoInicial = null,
  simulacion,
  onBack,
  onModificar,
  onResultado,
  onFormalizar,
}: EvaluacionYResultadoProps) {
  // Un borrador retomado con resultado previo muestra esa consulta tal
  // como quedó: la evaluación ya está persistida y no se puede volver a
  // lanzar con otros parámetros desde el asesor.
  const [fase, setFase] = useState<'origen' | 'evaluando' | 'resultado'>(
    resultadoInicial ? 'resultado' : 'origen',
  )
  const [origen, setOrigen] = useState<DatosEvaluacion>({
    origen: 'demo',
    escenarioMock: 'aprobado',
  })
  const [escenarios, setEscenarios] = useState<Record<string, string>>(
    ESCENARIOS_POR_DEFECTO,
  )
  const [resultado, setResultado] = useState<ResultadoEvaluacionCredito | null>(
    resultadoInicial,
  )
  const [error, setError] = useState<string | null>(null)
  const [formalizacionIniciada, setFormalizacionIniciada] = useState(false)
  // Borrador retomado con solicitud radicada pero sin resultado en el
  // contexto (guardado antes de persistirlo): se consulta el backend y,
  // si la evaluación ya existe, se muestra en vez de repetir la consulta.
  const [recuperando, setRecuperando] = useState(false)

  useEffect(() => {
    listarEscenariosMock()
      .then(setEscenarios)
      .catch(() => setEscenarios(ESCENARIOS_POR_DEFECTO))
  }, [])

  useEffect(() => {
    if (resultado || !idSolicitud) return
    let cancelado = false
    setRecuperando(true)
    listarAuditoriaSolicitud(idSolicitud)
      .then((lista) => {
        const ultima = lista
          .slice()
          .sort((a, b) => a.fecha_evaluacion.localeCompare(b.fecha_evaluacion))
          .pop()
        return ultima ? obtenerAuditoria(ultima.evaluacion_id) : null
      })
      .then((auditoria) => {
        if (cancelado || !auditoria) return
        const plazo =
          Number(auditoria.request?.plazo) || solicitud?.plazoMeses || 24
        const previo = resultadoDesdeApi(auditoria.resultado, plazo)
        setResultado(previo)
        onResultado?.(previo)
        setFase('resultado')
      })
      .catch(() => {
        // Sin evaluación previa o sin backend: el flujo sigue normal.
      })
      .finally(() => {
        if (!cancelado) setRecuperando(false)
      })
    return () => {
      cancelado = true
    }
    // Solo al montar: decide si hay evaluación persistida que mostrar.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const ejecutar = () => {
    setFase('evaluando')
    setError(null)

    if (!idSolicitud || !solicitud) {
      window.setTimeout(() => {
        const demo = crearResultadoDemo({
          decision: origen.origen === 'demo' ? 'APROBADO' : 'RECHAZADO',
          ingresosMensuales: solicitud?.ingresosMensuales ?? 4_500_000,
          plazoMeses: solicitud?.plazoMeses ?? 24,
        })
        setResultado(demo)
        onResultado?.(demo)
        setFase('resultado')
      }, 1200)
      return
    }

    evaluarSolicitud(
      idSolicitud,
      construirEvaluacionPayload(
        solicitud,
        {
          origen: origen.origen,
          escenarioMock: origen.escenarioMock,
        },
        {
          primerApellido: identidad?.apellidos
            ? primerApellido(identidad.apellidos)
            : undefined,
          tieneMultasRunt: validacion?.multasPendientes ?? false,
        },
      ),
    )
      .then((respuesta) => {
        const evaluado = resultadoDesdeApi(respuesta, solicitud.plazoMeses)
        setResultado(evaluado)
        onResultado?.(evaluado)
      })
      .catch((err: unknown) => {
        // 502 tiene dos orígenes: proxy sin backend vs backend con
        // DataCreditoError (Experian sin credenciales). Mostrar el detalle
        // evita el genérico "La evaluación no respondió".
        if (err instanceof ApiError) {
          const detalle =
            typeof err.detalle === 'string'
              ? err.detalle
              : JSON.stringify(err.detalle ?? '')
          if (err.status === 0) {
            setError(
              'La evaluación no respondió. Revisa la conexión e intenta de nuevo.',
            )
          } else if (err.status === 502) {
            setError(`Error 502 al evaluar: ${detalle}`)
          } else {
            setError(`Error ${err.status} al evaluar: ${detalle}`)
          }
        } else {
          setError(
            'La evaluación no respondió. Revisa la conexión e intenta de nuevo.',
          )
        }
      })
      .finally(() => setFase('resultado'))
  }

  const nombreSolicitante = identidad
    ? `${identidad.nombres} ${identidad.apellidos}`.trim()
    : 'Solicitante de demostración'

  return (
    <div className="evaluacion-resultado">
      <header className="evaluacion-resultado__header">
        <div className="evaluacion-resultado__header-copy">
          <p className="evaluacion-resultado__eyebrow">
            Originación Individual · Paso 5
          </p>
          <h1>Resultado y oferta</h1>
          <p className="evaluacion-resultado__subtitle">
            Consulta a centrales y evaluación de la solicitud
          </p>
        </div>
      </header>

      <SeguimientoOriginacion pasoActual={5} />

      {fase === 'origen' && recuperando && (
        <section className="evaluacion-resultado__evaluando" aria-live="polite">
          <LoaderCircle
            size={40}
            className="evaluacion-resultado__spinner"
            aria-hidden="true"
          />
          <h2>Recuperando la consulta</h2>
          <p>Verificando si esta solicitud ya fue evaluada.</p>
        </section>
      )}

      {fase === 'origen' && !recuperando && (
        <section className="evaluacion-resultado__origen">
          <div className="evaluacion-resultado__solicitante">
            <span aria-hidden="true">
              {nombreSolicitante
                .split(' ')
                .slice(0, 2)
                .map((p) => p.charAt(0))
                .join('')}
            </span>
            <div>
              <strong>{nombreSolicitante}</strong>
              <small>
                {identidad
                  ? `${identidad.tipoDocumento} ${identidad.numeroDocumento}`
                  : 'Modo demostración'}
              </small>
            </div>
          </div>

          <h2>Origen de la consulta</h2>
          <div
            className="evaluacion-resultado__origen-grupo"
            role="group"
            aria-label="Origen de datos del buró"
          >
            <label className="evaluacion-resultado__origen-opcion">
              <input
                type="radio"
                name="origen-consulta"
                checked={origen.origen === 'demo'}
                onChange={() =>
                  setOrigen((prev) => ({ ...prev, origen: 'demo' }))
                }
              />
              Escenario de demostración
              {origen.origen === 'demo' && (
                <select
                  value={origen.escenarioMock}
                  aria-label="Escenario simulado"
                  onClick={(e) => e.stopPropagation()}
                  onChange={(e) =>
                    setOrigen((prev) => ({
                      ...prev,
                      escenarioMock: e.target.value,
                    }))
                  }
                >
                  {Object.entries(escenarios).map(([codigo, descripcion]) => (
                    <option key={codigo} value={codigo}>
                      {descripcion || codigo}
                    </option>
                  ))}
                </select>
              )}
            </label>
            <label className="evaluacion-resultado__origen-opcion">
              <input
                type="radio"
                name="origen-consulta"
                checked={origen.origen === 'experian'}
                onChange={() =>
                  setOrigen((prev) => ({ ...prev, origen: 'experian' }))
                }
              />
              Experian en línea (requiere credenciales)
            </label>
          </div>

          {error && (
            <div className="evaluacion-resultado__error" role="alert">
              <AlertTriangle size={18} aria-hidden="true" />
              <p>{error}</p>
            </div>
          )}

          <div className="evaluacion-resultado__acciones">
            <Boton
              type="button"
              variante="secundario"
              iconoInicio={<ArrowLeft size={14} aria-hidden="true" />}
              onClick={onBack}
            >
              Volver al perfil económico
            </Boton>
            <Boton
              type="button"
              iconoFin={<ArrowRight size={15} aria-hidden="true" />}
              onClick={ejecutar}
            >
              Consultar centrales y evaluar
            </Boton>
          </div>
        </section>
      )}

      {fase === 'evaluando' && (
        <section className="evaluacion-resultado__evaluando" aria-live="polite">
          <LoaderCircle
            size={40}
            className="evaluacion-resultado__spinner"
            aria-hidden="true"
          />
          <h2>Consultando centrales de riesgo</h2>
          <p>
            Estamos aplicando las políticas de riesgo. Esto puede tomar unos
            segundos.
          </p>
        </section>
      )}

      {fase === 'resultado' && resultado && (
        <ResultadoCredito
          compacto
          resultado={resultado}
          idSolicitud={idSolicitud}
          simulacion={simulacion}
          solicitud={solicitud}
          formalizacionIniciada={formalizacionIniciada}
          onModificar={onModificar}
          onFormalizar={(oferta) => {
            setFormalizacionIniciada(true)
            onFormalizar?.(oferta)
          }}
        />
      )}

      {fase === 'resultado' && !resultado && error && (
        <section className="evaluacion-resultado__origen">
          <div className="evaluacion-resultado__error" role="alert">
            <AlertTriangle size={18} aria-hidden="true" />
            <p>{error}</p>
          </div>
          <div className="evaluacion-resultado__acciones">
            <Boton
              type="button"
              variante="secundario"
              onClick={() => setFase('origen')}
            >
              Volver a intentar
            </Boton>
          </div>
        </section>
      )}
    </div>
  )
}
