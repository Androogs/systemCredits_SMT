import { useEffect, useRef } from 'react'

interface NumeroFluidoProps {
  /** Valor final al que llega el conteo. */
  valor: number
  /** Da formato al entero mostrado (p. ej. currency, number). */
  formato?: (n: number) => string
  duracionMs?: number
  className?: string
}

const identidad = (n: number) => String(n)

/**
 * Conteo ascendente ease-out cúbico que escribe `textContent` directo
 * sobre el <span> vía rAF: la animación no dispara re-renders de React,
 * así páginas pesadas (Simulador, dashboard) no se redibujan a 60fps
 * mientras el número sube. Respeta prefers-reduced-motion.
 */
export default function NumeroFluido({
  valor,
  formato = identidad,
  duracionMs = 900,
  className,
}: NumeroFluidoProps) {
  const ref = useRef<HTMLSpanElement>(null)
  const desdeRef = useRef(0)
  const formatoRef = useRef(formato)
  formatoRef.current = formato

  useEffect(() => {
    const nodo = ref.current
    if (!nodo) return
    const pinta = (n: number) => {
      nodo.textContent = formatoRef.current(Math.round(n))
    }
    const reduceMotion = window.matchMedia(
      '(prefers-reduced-motion: reduce)',
    ).matches
    if (reduceMotion || !Number.isFinite(valor)) {
      desdeRef.current = valor
      pinta(valor)
      return
    }
    const desde = desdeRef.current
    if (desde === valor) {
      pinta(valor)
      return
    }
    const inicio = performance.now()
    let raf = 0
    const paso = (t: number) => {
      const p = Math.min(1, (t - inicio) / duracionMs)
      const actual = desde + (valor - desde) * (1 - Math.pow(1 - p, 3))
      desdeRef.current = actual
      pinta(actual)
      if (p < 1) raf = requestAnimationFrame(paso)
    }
    raf = requestAnimationFrame(paso)
    return () => cancelAnimationFrame(raf)
    // formatoRef siempre apunta al último formato: no reinicia la
    // animación cuando el padre re-renderiza con una arrow nueva.
  }, [valor, duracionMs])

  return (
    <span ref={ref} className={className}>
      {formatoRef.current(Math.round(desdeRef.current))}
    </span>
  )
}
