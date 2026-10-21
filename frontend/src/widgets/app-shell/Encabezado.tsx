import type { ReactNode } from 'react'

interface EncabezadoProps {
  title: string
  subtitle?: string
  actions?: ReactNode
}

export default function Encabezado({
  title,
  subtitle,
  actions,
}: EncabezadoProps) {
  return (
    <header className="flex min-h-16 items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-2 sm:px-6">
      <div className="min-w-0">
        <h1 className="truncate text-lg font-semibold text-slate-900">
          {title}
        </h1>
        {subtitle && (
          <p className="truncate text-xs text-slate-500">{subtitle}</p>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-2 sm:gap-3">{actions}</div>
    </header>
  )
}
