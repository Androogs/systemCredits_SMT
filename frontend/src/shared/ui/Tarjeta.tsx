import type { HTMLAttributes } from 'react'

interface TarjetaProps extends HTMLAttributes<HTMLDivElement> {
  className?: string
}

export default function Tarjeta({
  className = '',
  children,
  ...rest
}: TarjetaProps) {
  return (
    <div className={`card p-5 ${className}`} {...rest}>
      {children}
    </div>
  )
}
