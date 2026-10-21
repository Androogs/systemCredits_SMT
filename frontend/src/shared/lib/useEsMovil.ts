import { useEffect, useState } from 'react'

/**
 * True cuando el viewport es más angosto que `anchoMax` (default 640px,
 * el breakpoint `sm` de Tailwind). Se suscribe a cambios de matchMedia:
 * reacciona a resize, rotación y ventanas partidas.
 */
export function useEsMovil(anchoMax = 640): boolean {
  const [movil, setMovil] = useState(
    () =>
      typeof window !== 'undefined' &&
      window.matchMedia(`(max-width: ${anchoMax - 1}px)`).matches,
  )
  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${anchoMax - 1}px)`)
    const onChange = () => setMovil(mq.matches)
    onChange()
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [anchoMax])
  return movil
}
