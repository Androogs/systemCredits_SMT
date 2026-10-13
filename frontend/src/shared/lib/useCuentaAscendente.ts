import { useEffect, useRef, useState } from 'react'

/**
 * Anima un número desde su último valor mostrado hasta `objetivo` con
 * ease-out cúbico (arranca en 0 la primera vez — "de 0 a lo que hay").
 * Respeta prefers-reduced-motion devolviendo el objetivo de inmediato.
 */
export function useCuentaAscendente(
  objetivo: number,
  duracionMs = 900,
): number {
  const [reduceMotion] = useState(
    () =>
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  )
  const [valor, setValor] = useState(0)
  const desdeRef = useRef(0)

  useEffect(() => {
    if (reduceMotion || !Number.isFinite(objetivo)) {
      desdeRef.current = objetivo
      setValor(objetivo)
      return
    }
    const desde = desdeRef.current
    if (desde === objetivo) return
    const inicio = performance.now()
    let raf = 0
    const paso = (t: number) => {
      const p = Math.min(1, (t - inicio) / duracionMs)
      const suavizado = 1 - Math.pow(1 - p, 3)
      const actual = desde + (objetivo - desde) * suavizado
      desdeRef.current = actual
      setValor(actual)
      if (p < 1) raf = requestAnimationFrame(paso)
    }
    raf = requestAnimationFrame(paso)
    return () => cancelAnimationFrame(raf)
    // desdeRef conserva el último valor renderizado entre objetivos
  }, [objetivo, duracionMs, reduceMotion])

  return valor
}
