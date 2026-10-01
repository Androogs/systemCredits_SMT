import { LoaderCircle } from 'lucide-react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import './Boton.css'

export type VarianteBoton = 'primario' | 'secundario' | 'terciario' | 'peligro'
export type TamanoBoton = 'compacto' | 'normal'

interface BotonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: VarianteBoton
  tamano?: TamanoBoton
  cargando?: boolean
  iconoInicio?: ReactNode
  iconoFin?: ReactNode
}

function Boton({
  variante = 'primario',
  tamano = 'normal',
  cargando = false,
  iconoInicio,
  iconoFin,
  className = '',
  children,
  disabled,
  type = 'button',
  ...rest
}: BotonProps) {
  return (
    <button
      className={`boton boton--${variante} boton--${tamano} ${className}`.trim()}
      type={type}
      disabled={disabled || cargando}
      aria-busy={cargando || undefined}
      {...rest}
    >
      {cargando ? (
        <LoaderCircle
          className="boton__indicador-carga"
          size={16}
          aria-hidden="true"
        />
      ) : (
        iconoInicio
      )}
      <span>{children}</span>
      {!cargando && iconoFin}
    </button>
  )
}

export default Boton
