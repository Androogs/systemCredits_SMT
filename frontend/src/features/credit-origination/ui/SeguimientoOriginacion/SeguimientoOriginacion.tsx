import { useState } from 'react'
import { Check, ChevronDown, ChevronUp } from 'lucide-react'
import {
  etapasOriginacion,
  type PasoOriginacion,
} from '../../model/etapas-originacion'
import './SeguimientoOriginacion.css'

interface SeguimientoOriginacionProps {
  pasoActual: PasoOriginacion
}

function SeguimientoOriginacion({ pasoActual }: SeguimientoOriginacionProps) {
  const [expandido, setExpandido] = useState(false)
  const etapaActual = etapasOriginacion[pasoActual - 1]

  const fases = [
    { titulo: 'Identidad y solicitud', etapas: etapasOriginacion.slice(0, 6) },
    { titulo: 'Consulta y decisión', etapas: etapasOriginacion.slice(6) },
  ] as const

  return (
    <nav className="seguimiento" aria-label="Progreso de la solicitud">
      <div className="seguimiento__resumen">
        <span>
          Originación de crédito
          {etapaActual && <em> · {etapaActual.titulo}</em>}
        </span>
        <strong>Etapa {String(pasoActual).padStart(2, '0')} de 12</strong>
        <button
          type="button"
          className="seguimiento__toggle"
          aria-expanded={expandido}
          aria-controls="seguimiento-etapas"
          onClick={() => setExpandido((valor) => !valor)}
        >
          {expandido ? 'Ocultar etapas' : 'Ver etapas'}
          {expandido ? (
            <ChevronUp size={14} aria-hidden="true" />
          ) : (
            <ChevronDown size={14} aria-hidden="true" />
          )}
        </button>
        <div
          className="seguimiento__progreso"
          role="progressbar"
          aria-label="Progreso de originación"
          aria-valuemin={1}
          aria-valuemax={12}
          aria-valuenow={pasoActual}
        >
          <span
            style={{
              width: `${(pasoActual / etapasOriginacion.length) * 100}%`,
            }}
          />
        </div>
      </div>

      {expandido && (
        <div className="seguimiento__fases" id="seguimiento-etapas">
          {fases.map((fase, faseIndice) => (
            <section className="seguimiento__fase" key={fase.titulo}>
              <h2>
                <span>0{faseIndice + 1}</span>
                {fase.titulo}
              </h2>
              <ol
                className="seguimiento__etapas"
                aria-label={`Etapas ${faseIndice * 6 + 1} a ${faseIndice * 6 + 6}`}
                start={faseIndice * 6 + 1}
              >
                {fase.etapas.map((etapa, indice) => {
                  const posicion = faseIndice * 6 + indice + 1
                  const estado =
                    posicion < pasoActual
                      ? 'completada'
                      : posicion === pasoActual
                        ? 'actual'
                        : 'pendiente'

                  return (
                    <li
                      className={`seguimiento__etapa seguimiento__etapa--${estado}`}
                      key={etapa.titulo}
                      aria-current={estado === 'actual' ? 'step' : undefined}
                    >
                      <span
                        className="seguimiento__marcador"
                        aria-hidden="true"
                      >
                        {estado === 'completada' ? (
                          <Check size={14} strokeWidth={2.5} />
                        ) : (
                          String(posicion).padStart(2, '0')
                        )}
                      </span>
                      <span className="seguimiento__texto">
                        <strong>{etapa.titulo}</strong>
                        <small>{etapa.detalle}</small>
                      </span>
                    </li>
                  )
                })}
              </ol>
            </section>
          ))}
        </div>
      )}
    </nav>
  )
}

export default SeguimientoOriginacion
