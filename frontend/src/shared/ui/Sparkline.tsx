import { useId } from 'react'

interface Props {
  /** Serie de valores en orden cronológico (mismo bucket que la
      gráfica principal para que ambas cuenten lo mismo). */
  serie: number[]
  /** Color del trazo; por defecto gris (métrica no seleccionada). */
  color?: string
  className?: string
}

/** Sparkline SVG mínima: línea de 1.5px con relleno tenue, sin ejes.
    Un solo punto se dibuja como marca; serie vacía o todo-ceros
    dibuja una línea plana honesta en la base. */
export default function Sparkline({
  serie,
  color = '#94a3b8',
  className = '',
}: Props) {
  const idGradiente = useId()
  const W = 100
  const H = 28
  if (serie.length === 0) {
    return (
      <svg className={className} viewBox={`0 0 ${W} ${H}`} aria-hidden="true" />
    )
  }
  const max = Math.max(...serie)
  const min = Math.min(...serie, 0)
  const rango = max - min || 1
  const puntos = serie.map((v, i) => {
    const x = serie.length === 1 ? W / 2 : (i / (serie.length - 1)) * W
    // 2px de margen arriba y abajo para que el trazo no toque el borde.
    const y = H - 2 - ((v - min) / rango) * (H - 4)
    return [x, y] as const
  })
  const linea = puntos
    .map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`)
    .join(' ')
  const area = `0,${H} ${linea} ${W},${H}`
  return (
    <svg
      className={className}
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={idGradiente} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.25} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <polygon points={area} fill={`url(#${idGradiente})`} />
      <polyline
        points={linea}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  )
}
