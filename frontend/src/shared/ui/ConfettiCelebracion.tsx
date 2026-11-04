import type { CSSProperties } from 'react'
import './ConfettiCelebracion.css'

// Piezas de confetti deterministas para celebrar la aprobación.
const PIEZAS: CSSProperties[] = Array.from({ length: 26 }, (_, i) => {
  const paleta = [
    '#22c55e',
    '#0052a1',
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

/** Lluvia de confetti sobre el contenedor: absoluta, sin eventos y en
 *  bucle mientras el padre lo renderiza. El padre necesita
 *  `position: relative` y `overflow: hidden` para recortar las piezas
 *  en sus bordes. */
export default function ConfettiCelebracion() {
  return (
    <div className="confetti-celebracion" aria-hidden="true">
      {PIEZAS.map((estilo, i) => (
        <i key={i} style={estilo} />
      ))}
    </div>
  )
}
