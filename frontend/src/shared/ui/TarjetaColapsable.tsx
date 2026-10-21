import { ChevronDown } from 'lucide-react'
import { useId, useState, type ReactNode } from 'react'
import Tarjeta from './Tarjeta'

interface TarjetaColapsableProps {
  /** Cabecera de la tarjeta (suele llevar un icono + título). */
  titulo: ReactNode
  /** Texto breve visible junto al título mientras está cerrada
      (conteo de elementos, alcance: "9 documentos", "sin evidencias"). */
  resumen?: ReactNode
  /** Acciones junto al chevron, fuera del botón de pliegue (descargas,
      enlaces): siguen disponibles con la tarjeta cerrada. */
  acciones?: ReactNode
  /** Arranca desplegada. */
  abierto?: boolean
  className?: string
  children: ReactNode
}

/**
 * Tarjeta plegable para vistas densas: la cabecera siempre queda
 * visible con su resumen y el contenido solo se monta al abrir —
 * así las secciones pesadas (imágenes, tablas de auditoría) no
 * saturan la pantalla ni el DOM mientras no se consultan.
 */
export default function TarjetaColapsable({
  titulo,
  resumen,
  acciones,
  abierto = false,
  className = '',
  children,
}: TarjetaColapsableProps) {
  const [desplegada, setDesplegada] = useState(abierto)
  const idContenido = useId()
  return (
    <Tarjeta className={className}>
      <div className="flex items-center gap-3">
        <button
          type="button"
          aria-expanded={desplegada}
          aria-controls={idContenido}
          onClick={() => setDesplegada((v) => !v)}
          className="flex min-w-0 flex-1 items-center gap-2 py-0.5 text-left font-semibold text-slate-900"
        >
          {titulo}
          {resumen != null && !desplegada && (
            <span className="ml-1 truncate text-xs font-normal text-slate-500">
              {resumen}
            </span>
          )}
          <ChevronDown
            size={16}
            aria-hidden="true"
            className={`ml-auto shrink-0 text-slate-400 transition-transform duration-150 ${
              desplegada ? 'rotate-180' : ''
            }`}
          />
        </button>
        {acciones}
      </div>
      {desplegada && (
        <div id={idContenido} className="mt-4">
          {children}
        </div>
      )}
    </Tarjeta>
  )
}
