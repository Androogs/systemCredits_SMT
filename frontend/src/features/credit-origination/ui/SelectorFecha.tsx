import { useEffect, useMemo, useRef, useState } from 'react'
import { CalendarDays, ChevronLeft, ChevronRight } from 'lucide-react'
import './SelectorFecha.css'

/**
 * Selector de fecha propio: reemplaza el <input type="date"> nativo
 * (cuyo calendario no deja saltar de año — incómodo para nacimientos
 * y expediciones de hace décadas). Valor ISO 'YYYY-MM-DD', igual que
 * el input nativo, para no tocar el resto del formulario.
 */

const MESES = [
  'enero',
  'febrero',
  'marzo',
  'abril',
  'mayo',
  'junio',
  'julio',
  'agosto',
  'septiembre',
  'octubre',
  'noviembre',
  'diciembre',
]
const DIAS_SEMANA = ['LU', 'MA', 'MI', 'JU', 'VI', 'SA', 'DO']

const FORMATO_LARGO = new Intl.DateTimeFormat('es-CO', {
  day: 'numeric',
  month: 'long',
  year: 'numeric',
})

function aIso(anio: number, mes: number, dia: number) {
  return `${anio}-${String(mes + 1).padStart(2, '0')}-${String(dia).padStart(2, '0')}`
}

function deIso(iso: string): { anio: number; mes: number; dia: number } | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso)
  if (!m) return null
  const anio = Number(m[1])
  const mes = Number(m[2]) - 1
  const dia = Number(m[3])
  const d = new Date(anio, mes, dia)
  if (d.getFullYear() !== anio || d.getMonth() !== mes || d.getDate() !== dia)
    return null
  return { anio, mes, dia }
}

const HOY = new Date()
const HOY_ISO = aIso(HOY.getFullYear(), HOY.getMonth(), HOY.getDate())

interface SelectorFechaProps {
  id?: string
  value: string
  onChange: (iso: string) => void
  onBlur?: () => void
  disabled?: boolean
  invalid?: boolean
  placeholder?: string
  /** Tope seleccionable (ISO); por defecto hoy — ni nacimientos ni
      expediciones pueden ser futuras. */
  max?: string
  anioMinimo?: number
}

export default function SelectorFecha({
  id,
  value,
  onChange,
  onBlur,
  disabled = false,
  invalid = false,
  placeholder = 'Selecciona la fecha',
  max = HOY_ISO,
  anioMinimo = 1920,
}: SelectorFechaProps) {
  const [abierto, setAbierto] = useState(false)
  const raiz = useRef<HTMLDivElement>(null)

  const seleccion = deIso(value)
  const maximo = deIso(max) ?? deIso(HOY_ISO)!

  // El mes visible arranca en la fecha elegida (o en hoy si no hay).
  const [vista, setVista] = useState(() => ({
    anio: seleccion?.anio ?? maximo.anio,
    mes: seleccion?.mes ?? maximo.mes,
  }))

  const cerrar = () => {
    setAbierto(false)
    onBlur?.()
  }

  useEffect(() => {
    if (!abierto) return
    const alClick = (e: MouseEvent) => {
      if (raiz.current && !raiz.current.contains(e.target as Node)) cerrar()
    }
    const alEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') cerrar()
    }
    document.addEventListener('mousedown', alClick)
    document.addEventListener('keydown', alEscape)
    return () => {
      document.removeEventListener('mousedown', alClick)
      document.removeEventListener('keydown', alEscape)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [abierto])

  const anios = useMemo(() => {
    const lista: number[] = []
    for (let a = maximo.anio; a >= anioMinimo; a--) lista.push(a)
    return lista
  }, [maximo.anio, anioMinimo])

  /** Celdas del mes: lunes primero; los días vecinos van atenuados. */
  const celdas = useMemo(() => {
    const primero = new Date(vista.anio, vista.mes, 1)
    const offset = (primero.getDay() + 6) % 7 // lunes = 0
    const diasMes = new Date(vista.anio, vista.mes + 1, 0).getDate()
    const diasPrev = new Date(vista.anio, vista.mes, 0).getDate()
    const filas: { iso: string; dia: number; propio: boolean }[] = []
    for (let i = 0; i < 42; i++) {
      const n = i - offset + 1
      if (n < 1) {
        const d = diasPrev + n
        filas.push({
          iso: aIso(
            vista.mes === 0 ? vista.anio - 1 : vista.anio,
            (vista.mes + 11) % 12,
            d,
          ),
          dia: d,
          propio: false,
        })
      } else if (n > diasMes) {
        const d = n - diasMes
        filas.push({
          iso: aIso(
            vista.mes === 11 ? vista.anio + 1 : vista.anio,
            (vista.mes + 1) % 12,
            d,
          ),
          dia: d,
          propio: false,
        })
      } else {
        filas.push({
          iso: aIso(vista.anio, vista.mes, n),
          dia: n,
          propio: true,
        })
      }
    }
    return filas
  }, [vista])

  const moverMes = (delta: number) =>
    setVista((v) => {
      const total = v.anio * 12 + v.mes + delta
      return { anio: Math.floor(total / 12), mes: ((total % 12) + 12) % 12 }
    })

  const elegir = (iso: string) => {
    if (iso > max) return
    onChange(iso)
    cerrar()
  }

  const etiqueta = seleccion
    ? FORMATO_LARGO.format(
        new Date(seleccion.anio, seleccion.mes, seleccion.dia),
      )
    : ''

  return (
    <div className="selector-fecha" ref={raiz}>
      <button
        id={id}
        type="button"
        className={`selector-fecha__trigger${value ? '' : ' is-empty'}`}
        disabled={disabled}
        aria-invalid={invalid}
        aria-haspopup="dialog"
        aria-expanded={abierto}
        onClick={() => {
          if (!abierto && seleccion)
            setVista({ anio: seleccion.anio, mes: seleccion.mes })
          setAbierto((a) => !a)
        }}
      >
        <CalendarDays size={16} aria-hidden="true" />
        <span>{etiqueta || placeholder}</span>
      </button>

      {abierto && (
        <div
          className="selector-fecha__popover"
          role="dialog"
          aria-label="Elegir fecha"
        >
          <div className="selector-fecha__cabecera">
            <button
              type="button"
              className="selector-fecha__nav"
              aria-label="Mes anterior"
              onClick={() => moverMes(-1)}
            >
              <ChevronLeft size={16} />
            </button>
            <div className="selector-fecha__selectores">
              <select
                aria-label="Mes"
                value={vista.mes}
                onChange={(e) =>
                  setVista((v) => ({ ...v, mes: Number(e.target.value) }))
                }
              >
                {MESES.map((m, i) => (
                  <option key={m} value={i}>
                    {m}
                  </option>
                ))}
              </select>
              <select
                aria-label="Año"
                value={vista.anio}
                onChange={(e) =>
                  setVista((v) => ({ ...v, anio: Number(e.target.value) }))
                }
              >
                {anios.map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="button"
              className="selector-fecha__nav"
              aria-label="Mes siguiente"
              onClick={() => moverMes(1)}
            >
              <ChevronRight size={16} />
            </button>
          </div>

          <div className="selector-fecha__semana" aria-hidden="true">
            {DIAS_SEMANA.map((d) => (
              <span key={d}>{d}</span>
            ))}
          </div>

          <div className="selector-fecha__grid" role="grid">
            {celdas.map((c) => {
              const futura = c.iso > max
              const clases = [
                'selector-fecha__dia',
                c.propio ? '' : 'is-ajeno',
                c.iso === value ? 'is-selected' : '',
                c.iso === HOY_ISO ? 'is-today' : '',
              ]
                .filter(Boolean)
                .join(' ')
              return (
                <button
                  key={c.iso}
                  type="button"
                  role="gridcell"
                  className={clases}
                  disabled={futura}
                  aria-selected={c.iso === value}
                  aria-label={FORMATO_LARGO.format(
                    new Date(`${c.iso}T00:00:00`),
                  )}
                  onClick={() => elegir(c.iso)}
                >
                  {c.dia}
                </button>
              )
            })}
          </div>

          <div className="selector-fecha__pie">
            <button
              type="button"
              className="selector-fecha__accion"
              onClick={() => {
                onChange('')
                cerrar()
              }}
            >
              Borrar
            </button>
            <button
              type="button"
              className="selector-fecha__accion is-primary"
              onClick={() => elegir(HOY_ISO)}
            >
              Hoy
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
