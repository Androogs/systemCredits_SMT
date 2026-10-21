import Skeleton from './Skeleton'

/** Fallback de Suspense mientras llega el chunk de la página. */
export default function CargandoPagina() {
  return (
    <div className="p-6 md:p-8" role="status" aria-label="Cargando">
      <Skeleton className="mb-4 h-7 w-48" />
      <Skeleton className="mb-3 h-4 w-full max-w-lg" />
      <Skeleton className="mb-6 h-4 w-3/4 max-w-md" />
      <Skeleton className="h-40 w-full rounded-xl" />
      <span className="sr-only">Cargando…</span>
    </div>
  )
}
