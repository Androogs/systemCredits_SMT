import { useId, useState, type InputHTMLAttributes } from 'react'
import {
  acotar,
  limpiarDecimal,
  limpiarEntero,
  parsearNumerico,
} from '../lib/campoNumerico'

interface CampoNumericoProps extends Omit<
  InputHTMLAttributes<HTMLInputElement>,
  'value' | 'onChange' | 'type'
> {
  label?: string
  error?: string
  /** null o 0 se muestran como campo vacío (nada de "0" pegado). */
  value: number | null
  onValor?: (valor: number | null) => void
  /** Permite decimales; acepta coma o punto. */
  decimales?: boolean
  /** Separador de miles es-CO cuando el campo no está enfocado. */
  formatoMiles?: boolean
  /** Muestra "0" en vez de vacío cuando 0 es un dato válido (parámetros). */
  mostrarCero?: boolean
  /** Acota el valor al salir del campo (datos fuera de rango). */
  minimo?: number
  maximo?: number
  /** Clases del input (ej. `input-base`). */
  className?: string
  /** Clases del contenedor cuando hay label/error. */
  contenedorClassName?: string
}

/**
 * Input numérico con texto crudo mientras está enfocado: se puede
 * vaciar, reescribir sin ceros pegados y digitar decimales con coma o
 * punto. Al perder el foco muestra el valor (con miles si aplica).
 */
export default function CampoNumerico({
  label,
  error,
  value,
  onValor,
  decimales = false,
  formatoMiles = false,
  mostrarCero = false,
  minimo,
  maximo,
  className = '',
  contenedorClassName = '',
  id,
  onFocus,
  onBlur,
  'aria-describedby': ariaDescribedBy,
  'aria-invalid': ariaInvalid,
  ...rest
}: CampoNumericoProps) {
  const idGenerado = useId()
  const idControl = id ?? idGenerado
  const idError = error ? `${idControl}-error` : undefined
  const [enfocado, setEnfocado] = useState(false)
  const [texto, setTexto] = useState('')

  const valorVisible = () => {
    if (value == null || (value === 0 && !mostrarCero)) return ''
    return formatoMiles ? value.toLocaleString('es-CO') : String(value)
  }

  return (
    <div
      className={contenedorClassName}
      style={!label && !error ? { display: 'contents' } : undefined}
    >
      {label && (
        <label className="label-base" htmlFor={idControl}>
          {label}
        </label>
      )}
      <input
        {...rest}
        id={idControl}
        className={className || undefined}
        type="text"
        inputMode={decimales ? 'decimal' : 'numeric'}
        value={enfocado ? texto : valorVisible()}
        aria-invalid={error ? true : ariaInvalid}
        aria-describedby={
          [ariaDescribedBy, idError].filter(Boolean).join(' ') || undefined
        }
        onFocus={(e) => {
          setTexto(
            value == null || (value === 0 && !mostrarCero) ? '' : String(value),
          )
          setEnfocado(true)
          onFocus?.(e)
        }}
        onChange={(e) => {
          const limpio = decimales
            ? limpiarDecimal(e.target.value)
            : limpiarEntero(e.target.value)
          setTexto(limpio)
          onValor?.(parsearNumerico(limpio))
        }}
        onBlur={(e) => {
          setEnfocado(false)
          if (value != null) {
            const acotado = acotar(value, minimo, maximo)
            if (acotado !== value) onValor?.(acotado)
          }
          onBlur?.(e)
        }}
      />
      {error && (
        <p id={idError} className="mt-1 text-xs text-red-500" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
