import {
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type InputHTMLAttributes,
  type Ref,
} from 'react'
import {
  acotar,
  formatearMiles,
  limpiarDecimal,
  limpiarDecimalMiles,
  limpiarEntero,
  parsearNumerico,
  posicionTrasDigitos,
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
  /** Separador de miles es-CO al digitar y al salir del campo. */
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
  /** Ref al input (se encadena con la ref interna del cursor). */
  inputRef?: Ref<HTMLInputElement>
}

/**
 * Input numérico con miles es-CO mientras se digita: "1234567" se ve
 * "1.234.567" sin perder la posición del cursor. Con `formatoMiles` +
 * `decimales`, la coma es el separador decimal ("1.234,5"). Se puede
 * vaciar, reescribir sin ceros pegados y digitar decimales con coma.
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
  inputRef: refExterno,
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
  // `texto` siempre guarda el valor limpio ("1234567.89"); lo que se ve
  // enfocado es su versión formateada.
  const [texto, setTexto] = useState('')
  const inputRef = useRef<HTMLInputElement | null>(null)
  const cursorPendiente = useRef<number | null>(null)

  const valorVisible = () => {
    if (value == null || (value === 0 && !mostrarCero)) return ''
    return formatoMiles ? value.toLocaleString('es-CO') : String(value)
  }

  const limpiar = (bruto: string) =>
    decimales
      ? formatoMiles
        ? limpiarDecimalMiles(bruto)
        : limpiarDecimal(bruto)
      : limpiarEntero(bruto)

  const visibleEnfocado = () => (formatoMiles ? formatearMiles(texto) : texto)

  // Tras re-render con el texto formateado, el cursor vuelve a quedar
  // después de los mismos dígitos que tenía a su izquierda.
  useLayoutEffect(() => {
    if (cursorPendiente.current != null) {
      inputRef.current?.setSelectionRange(
        cursorPendiente.current,
        cursorPendiente.current,
      )
      cursorPendiente.current = null
    }
  }, [texto])

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
        ref={(el) => {
          inputRef.current = el
          if (typeof refExterno === 'function') refExterno(el)
          else if (refExterno) refExterno.current = el
        }}
        id={idControl}
        className={className || undefined}
        type="text"
        inputMode={decimales ? 'decimal' : 'numeric'}
        value={enfocado ? visibleEnfocado() : valorVisible()}
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
          const el = e.target
          const caret = el.selectionStart ?? el.value.length
          const digitosIzq = el.value.slice(0, caret).replace(/\D/g, '').length
          const limpio = limpiar(el.value)
          setTexto(limpio)
          onValor?.(parsearNumerico(limpio))
          if (formatoMiles) {
            cursorPendiente.current = posicionTrasDigitos(
              formatearMiles(limpio),
              digitosIzq,
            )
          }
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
