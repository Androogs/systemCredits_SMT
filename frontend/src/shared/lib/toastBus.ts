/**
 * Bus de notificaciones toast: desacopla el QueryClient (y otros emisores
 * no-React) del componente que renderiza la pila. D83.
 */

export type TipoToast = 'error' | 'exito' | 'info'

export interface ToastEntrada {
  tipo: TipoToast
  mensaje: string
  titulo?: string
}

type Listener = (t: ToastEntrada) => void

const listeners = new Set<Listener>()
let ultimoMensaje = ''
let ultimoInstante = 0

export function emitirToast(t: ToastEntrada): void {
  // Dedupe: varias consultas pueden fallar a la vez con el mismo error de
  // red; un solo toast basta.
  const ahora = Date.now()
  if (t.mensaje === ultimoMensaje && ahora - ultimoInstante < 4_000) return
  ultimoMensaje = t.mensaje
  ultimoInstante = ahora
  listeners.forEach((l) => l(t))
}

export function suscribirToasts(l: Listener): () => void {
  listeners.add(l)
  return () => {
    listeners.delete(l)
  }
}
