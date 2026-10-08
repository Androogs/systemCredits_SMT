interface SkeletonProps {
  className?: string
}

/** Bloque gris pulsante que reserva el espacio del contenido mientras carga. */
export default function Skeleton({ className = '' }: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      className={`animate-pulse rounded-md bg-slate-200 ${className}`}
    />
  )
}

interface FilasSkeletonProps {
  /** Cuántas filas de relleno pintar (aproxima la altura final de la tabla). */
  filas?: number
  columnas: number
}

/** Filas placeholder para el tbody de una tabla mientras llegan los datos. */
export function FilasSkeleton({ filas = 4, columnas }: FilasSkeletonProps) {
  return (
    <>
      {Array.from({ length: filas }, (_, i) => (
        <tr key={i} aria-hidden="true" className="border-b border-slate-100">
          {Array.from({ length: columnas }, (_, j) => (
            <td key={j} className="px-5 py-4">
              <Skeleton className="h-4 w-full" />
            </td>
          ))}
        </tr>
      ))}
    </>
  )
}
