import { AlertCircle, CheckCircle2, Info, TriangleAlert } from 'lucide-react'
import type { HTMLAttributes, ReactNode } from 'react'
import './Alerta.css'

export type VarianteAlerta = 'informacion' | 'exito' | 'advertencia' | 'error'

interface AlertaProps extends HTMLAttributes<HTMLDivElement> {
  variante?: VarianteAlerta
  titulo?: string
  children: ReactNode
}

const iconos = {
  informacion: Info,
  exito: CheckCircle2,
  advertencia: TriangleAlert,
  error: AlertCircle,
}

function Alerta({
  variante = 'informacion',
  titulo,
  children,
  className = '',
  role,
  ...rest
}: AlertaProps) {
  const Icono = iconos[variante]
  const rol = role ?? (variante === 'error' ? 'alert' : 'status')

  return (
    <div
      className={`alerta alerta--${variante} ${className}`.trim()}
      role={rol}
      aria-live={rol === 'alert' ? 'assertive' : 'polite'}
      {...rest}
    >
      <Icono className="alerta__icono" size={18} aria-hidden="true" />
      <div className="alerta__contenido">
        {titulo && <strong className="alerta__titulo">{titulo}</strong>}
        <div>{children}</div>
      </div>
    </div>
  )
}

export default Alerta
