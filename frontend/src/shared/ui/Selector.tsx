import { useId, type SelectHTMLAttributes } from 'react'

interface SelectorProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  options: { value: string; label: string }[]
  error?: string
  className?: string
}

export default function Selector({
  label,
  options,
  error,
  className = '',
  id,
  'aria-describedby': ariaDescribedBy,
  'aria-invalid': ariaInvalid,
  ...rest
}: SelectorProps) {
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
      <select
        id={idControl}
        className="input-base"
        aria-invalid={error ? true : ariaInvalid}
        aria-describedby={
          [ariaDescribedBy, idError].filter(Boolean).join(' ') || undefined
        }
        {...rest}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      {error && (
        <p id={idError} className="mt-1 text-xs text-red-500" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
