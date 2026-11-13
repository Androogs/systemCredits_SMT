import { useEffect, useRef, useState } from 'react'
import { Check, ChevronDown, PenLine } from 'lucide-react'
import { currency } from '../../../shared/lib/formatters'
import type { VehiculoCatalogoApi } from '../api/originacionApi'
import './SelectorMarca.css'

interface SelectorVehiculoProps {
  vehiculos: VehiculoCatalogoApi[]
  value: string
  disabled?: boolean
  onElegir: (referencia: string) => void
  /** El asesor escribe una referencia fuera del listado (campo libre). */
  onOtra: () => void
}

/**
 * Listado de motos del catálogo vigente con el mismo estilo del
 * selector de marca (botón + listbox propio — el <select> nativo no
 * muestra precio ni comparte el estilo). Al final, «Otra referencia…»
 * devuelve el campo libre para una moto no listada.
 */
export default function SelectorVehiculo({
  vehiculos,
  value,
  disabled,
  onElegir,
  onOtra,
}: SelectorVehiculoProps) {
  const [abierto, setAbierto] = useState(false)
  const raiz = useRef<HTMLDivElement>(null)

  // Cierra el menú al hacer clic fuera o con Escape.
  useEffect(() => {
    if (!abierto) return
    const alHacerClic = (e: MouseEvent) => {
      if (!raiz.current?.contains(e.target as Node)) setAbierto(false)
    }
    const alTeclar = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setAbierto(false)
    }
    document.addEventListener('mousedown', alHacerClic)
    document.addEventListener('keydown', alTeclar)
    return () => {
      document.removeEventListener('mousedown', alHacerClic)
      document.removeEventListener('keydown', alTeclar)
    }
  }, [abierto])

  const claseOpcion = (activa: boolean) =>
    'selector-marca__opcion' + (activa ? ' selector-marca__opcion--activa' : '')

  return (
    <div className="selector-marca" ref={raiz}>
      <button
        type="button"
        className="input-base selector-marca__boton"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={abierto}
        onClick={() => setAbierto((v) => !v)}
      >
        <span className={value ? undefined : 'selector-marca__vacio'}>
          {value || 'Selecciona la moto…'}
        </span>
        <ChevronDown
          size={15}
          aria-hidden="true"
          className={abierto ? 'selector-marca__chevron--arriba' : undefined}
        />
      </button>

      {abierto && (
        <ul
          className="selector-marca__menu"
          role="listbox"
          aria-label="Referencia"
        >
          {vehiculos.map((v) => (
            <li key={v.id_vehiculo_catalogo}>
              <button
                type="button"
                role="option"
                aria-selected={value === v.referencia}
                className={claseOpcion(value === v.referencia)}
                onClick={() => {
                  onElegir(v.referencia)
                  setAbierto(false)
                }}
              >
                <span>{v.referencia}</span>
                <span className="selector-vehiculo__precio">
                  {currency(Number(v.precio_lista))}
                </span>
                {value === v.referencia && (
                  <Check size={14} aria-hidden="true" />
                )}
              </button>
            </li>
          ))}
          <li>
            <button
              type="button"
              role="option"
              aria-selected={false}
              className={claseOpcion(false)}
              onClick={() => {
                onOtra()
                setAbierto(false)
              }}
            >
              <span>Otra referencia…</span>
              <PenLine size={13} aria-hidden="true" />
            </button>
          </li>
        </ul>
      )}
    </div>
  )
}
