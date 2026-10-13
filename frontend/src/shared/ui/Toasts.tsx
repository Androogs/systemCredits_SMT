import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react'
import { suscribirToasts, type ToastEntrada } from '../lib/toastBus'

interface ToastItem extends ToastEntrada {
  id: number
}

const ICONOS = {
  error: AlertTriangle,
  exito: CheckCircle2,
  info: Info,
}

const ESTILOS = {
  error: 'border-red-200 bg-red-50 text-red-800',
  exito: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  info: 'border-brand-200 bg-brand-50 text-brand-800',
} as const

const DURACION_MS = 5_200
const MAX_TOASTS = 3

let secuencia = 0

/** Pila de toasts global; se monta una vez en App. */
export default function Toasts() {
  const [items, setItems] = useState<ToastItem[]>([])

  useEffect(
    () =>
      suscribirToasts((entrada) => {
        const id = ++secuencia
        setItems((prev) => [
          ...prev.slice(-(MAX_TOASTS - 1)),
          { ...entrada, id },
        ])
        window.setTimeout(
          () => setItems((prev) => prev.filter((i) => i.id !== id)),
          DURACION_MS,
        )
      }),
    [],
  )

  if (items.length === 0) return null

  return (
    <div
      className="pointer-events-none fixed inset-x-4 bottom-4 z-[80] flex flex-col gap-2 sm:inset-x-auto sm:bottom-auto sm:right-4 sm:top-4 sm:w-[22rem]"
      aria-live="polite"
    >
      {items.map((t) => {
        const Icono = ICONOS[t.tipo]
        return (
          <div
            key={t.id}
            role={t.tipo === 'error' ? 'alert' : 'status'}
            className={`pointer-events-auto flex items-start gap-2.5 rounded-xl border px-3.5 py-3 text-sm shadow-lg shadow-slate-900/10 ${ESTILOS[t.tipo]}`}
          >
            <Icono size={17} className="mt-0.5 shrink-0" aria-hidden="true" />
            <div className="min-w-0 flex-1">
              {t.titulo && <p className="font-semibold">{t.titulo}</p>}
              <p className="break-words">{t.mensaje}</p>
            </div>
            <button
              type="button"
              onClick={() =>
                setItems((prev) => prev.filter((i) => i.id !== t.id))
              }
              className="rounded-md p-0.5 opacity-60 transition hover:opacity-100"
              aria-label="Cerrar notificación"
            >
              <X size={14} />
            </button>
          </div>
        )
      })}
    </div>
  )
}
