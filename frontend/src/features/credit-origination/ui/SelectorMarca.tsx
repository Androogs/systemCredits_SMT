import { useEffect, useRef, useState } from 'react'
import { Check, ChevronDown } from 'lucide-react'
import { MARCAS_VEHICULO, SUBMARCAS_AUTECO } from '../model/concesionarios'
import './SelectorMarca.css'

interface SelectorMarcaProps {
  value: string
  disabled?: boolean
  onChange: (marca: string) => void
}

/** Única marca con submenú propio (marca distribuidora → marcas). */
const MARCA_PADRE = 'Auteco'

/**
 * Selector de marca con submenú desplegable para Auteco (Ceronte,
 * Kymco, TVS, Victory, Zontes). Reemplaza al <select> nativo, que no
 * admite submenús; conserva el estilo .input-base.
 */
export default function SelectorMarca({
  value,
  disabled,
  onChange,
}: SelectorMarcaProps) {
  const [abierto, setAbierto] = useState(false)
  const [subAbierto, setSubAbierto] = useState(false)
  const raiz = useRef<HTMLDivElement>(null)

  const cerrar = () => {
    setAbierto(false)
    setSubAbierto(false)
  }

  // Cierra el menú al hacer clic fuera o con Escape.
  useEffect(() => {
    if (!abierto) return
    const alHacerClic = (e: MouseEvent) => {
      if (!raiz.current?.contains(e.target as Node)) cerrar()
    }
    const alTeclar = (e: KeyboardEvent) => {
      if (e.key === 'Escape') cerrar()
    }
    document.addEventListener('mousedown', alHacerClic)
    document.addEventListener('keydown', alTeclar)
    return () => {
      document.removeEventListener('mousedown', alHacerClic)
      document.removeEventListener('keydown', alTeclar)
    }
  }, [abierto])

  const elegir = (marca: string) => {
    onChange(marca)
    cerrar()
  }

  const autecoActivo = value === MARCA_PADRE || SUBMARCAS_AUTECO.includes(value)

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
          {value || 'Selecciona una opción…'}
        </span>
        <ChevronDown
          size={15}
          aria-hidden="true"
          className={abierto ? 'selector-marca__chevron--arriba' : undefined}
        />
      </button>

      {abierto && (
        <ul className="selector-marca__menu" role="listbox" aria-label="Marca">
          {MARCAS_VEHICULO.map((m) =>
            m === MARCA_PADRE ? (
              <li
                key={m}
                className="selector-marca__ancla"
                // Solo el ratón abre/cierra por hover; el táctil usa el
                // clic de abajo (pointerenter sintético de iOS rompería
                // el toggle si se combinaran).
                onPointerEnter={(e) => {
                  if (e.pointerType === 'mouse') setSubAbierto(true)
                }}
                onPointerLeave={(e) => {
                  if (e.pointerType === 'mouse') setSubAbierto(false)
                }}
              >
                <button
                  type="button"
                  role="option"
                  aria-selected={value === m}
                  aria-haspopup="true"
                  aria-expanded={subAbierto}
                  className={claseOpcion(autecoActivo)}
                  onClick={() => setSubAbierto((v) => !v)}
                >
                  <span>{m}</span>
                  <ChevronDown
                    size={14}
                    aria-hidden="true"
                    className={
                      subAbierto ? 'selector-marca__flecha--arriba' : undefined
                    }
                  />
                </button>
                {subAbierto && (
                  <ul
                    className="selector-marca__submenu"
                    role="group"
                    aria-label={`Marcas ${m}`}
                  >
                    {SUBMARCAS_AUTECO.map((s) => (
                      <li key={s}>
                        <button
                          type="button"
                          role="option"
                          aria-selected={value === s}
                          className={claseOpcion(value === s)}
                          onClick={() => elegir(s)}
                        >
                          <span>{s}</span>
                          {value === s && (
                            <Check size={14} aria-hidden="true" />
                          )}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ) : (
              <li key={m}>
                <button
                  type="button"
                  role="option"
                  aria-selected={value === m}
                  className={claseOpcion(value === m)}
                  onClick={() => elegir(m)}
                >
                  <span>{m}</span>
                  {value === m && <Check size={14} aria-hidden="true" />}
                </button>
              </li>
            ),
          )}
        </ul>
      )}
    </div>
  )
}
