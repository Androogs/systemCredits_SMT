import { useId, type InputHTMLAttributes, type ReactNode } from 'react'

interface CampoEntradaProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: ReactNode
  error?: string
  className?: string
}

export default function CampoEntrada({
  label,
  error,
  className = '',
  id,
  'aria-describedby': ariaDescribedBy,
  'aria-invalid': ariaInvalid,
  ...rest
}: CampoEntradaProps) {
  const idGenerado = useId()
  const idControl = id ?? idGenerado
  const idError = error ? `${idControl}-error` : undefined

  return (
    <div className={className}>
      {label && (
        <label className="label-base" htmlFor={idControl}>
          {label}
        </label>
      )}
      <input
        id={idControl}
        className="input-base"
        aria-invalid={error ? true : ariaInvalid}
        aria-describedby={
          [ariaDescribedBy, idError].filter(Boolean).join(' ') || undefined
        }
        {...rest}
      />
      {error && (
        <p id={idError} className="mt-1 text-xs text-red-500" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
