import { useEffect, useMemo, useRef, useState } from 'react'
import type { RefObject } from 'react'
import { NavLink } from 'react-router-dom'
import type { LucideIcon } from 'lucide-react'
import {
  LayoutDashboard,
  FilePlus2,
  ListChecks,
  LogOut,
  Settings2,
  PanelLeftClose,
  PanelLeftOpen,
  Briefcase,
  Calculator,
  X,
  UserCog,
  ShieldCheck,
} from 'lucide-react'
import { guardarRol, useRol } from '../../shared/lib/sesion'

interface ItemNav {
  to: string
  label: string
  icon: LucideIcon
  badge?: number
}

const nav: ItemNav[] = [
  { to: '/dashboard', label: 'Resumen', icon: LayoutDashboard },
  { to: '/asesor', label: 'Panel asesor', icon: Briefcase },
  { to: '/solicitudes', label: 'Solicitudes', icon: ListChecks },
  { to: '/nueva-solicitud', label: 'Nueva solicitud', icon: FilePlus2 },
  { to: '/simulador', label: 'Simulador', icon: Calculator },
  { to: '/ajustes', label: 'Ajustes', icon: Settings2 },
]

export default function BarraLateral({
  onLogout,
  mobileMenuOpen,
  onMobileMenuChange,
  botonMenuRef,
}: {
  onLogout: () => void
  mobileMenuOpen: boolean
  onMobileMenuChange: (open: boolean) => void
  botonMenuRef: RefObject<HTMLButtonElement | null>
}) {
  const [collapsed, setCollapsed] = useState(false)
  const menuMovilAbierto = mobileMenuOpen
  const setMenuMovilAbierto = onMobileMenuChange
  const [esMovil, setEsMovil] = useState(
    () => window.matchMedia('(max-width: 767.98px)').matches,
  )
  const rol = useRol()
  const itemsNav = useMemo<ItemNav[]>(() => [...nav], [])
  const botonCerrarRef = useRef<HTMLButtonElement>(null)
  const asideRef = useRef<HTMLElement>(null)
  const menuEstabaAbierto = useRef(false)

  useEffect(() => {
    const media = window.matchMedia('(max-width: 767.98px)')
    const actualizar = (event: MediaQueryListEvent) => {
      setEsMovil(event.matches)
      if (!event.matches) {
        setMenuMovilAbierto(false)
        setCollapsed(false)
      }
    }
    media.addEventListener('change', actualizar)
    return () => media.removeEventListener('change', actualizar)
  }, [setMenuMovilAbierto])

  useEffect(() => {
    if (menuMovilAbierto) {
      botonCerrarRef.current?.focus()
    } else if (menuEstabaAbierto.current) {
      botonMenuRef.current?.focus()
    }
    menuEstabaAbierto.current = menuMovilAbierto
  }, [menuMovilAbierto, botonMenuRef])

  useEffect(() => {
    if (!menuMovilAbierto) return
    const cerrarConEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMenuMovilAbierto(false)
        return
      }
      if (event.key !== 'Tab') return

      const focusable = asideRef.current?.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled])',
      )
      if (!focusable?.length) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    window.addEventListener('keydown', cerrarConEscape)
    return () => window.removeEventListener('keydown', cerrarConEscape)
  }, [menuMovilAbierto, setMenuMovilAbierto])

  const cerrarMenu = () => {
    if (window.matchMedia('(max-width: 767.98px)').matches) {
      setMenuMovilAbierto(false)
    } else {
      setCollapsed(true)
    }
  }

  return (
    <>
      {/* BACKDROP - SOLO MÓVIL */}
      <div
        role="presentation"
        aria-hidden="true"
        onClick={() => setMenuMovilAbierto(false)}
        className={`
          md:hidden fixed inset-0 z-40 bg-black/50 backdrop-blur-sm
          cursor-pointer transition-opacity duration-300
          ${menuMovilAbierto ? 'opacity-100' : 'opacity-0 pointer-events-none'}
        `}
      />

      <aside
        ref={asideRef}
        id="sidebar-nav"
        role={esMovil && menuMovilAbierto ? 'dialog' : undefined}
        aria-label="Menú principal"
        aria-modal={esMovil && menuMovilAbierto ? true : undefined}
        inert={esMovil && !menuMovilAbierto}
        className={`
        fixed md:sticky inset-y-0 left-0 top-0 z-50 md:z-auto
        flex flex-col border-r border-white/10 bg-[rgba(0,0,51,1)]
        h-screen w-64 shrink-0
        transition-all duration-300 ease-in-out
        ${menuMovilAbierto ? 'translate-x-0' : '-translate-x-full'}
        ${
          collapsed
            ? 'md:w-[4.25rem] md:translate-x-0 md:opacity-100 md:overflow-hidden'
            : 'md:w-64 md:translate-x-0 md:opacity-100'
        }
      `}
      >
        {/* HEADER - FIJO */}
        <div
          className={`flex items-center h-20 border-b border-white/10 px-4 gap-2 shrink-0 ${
            collapsed ? 'md:justify-center md:px-2' : ''
          }`}
        >
          <img
            src="/brand/pacifico-blancos.png"
            alt="Inversiones Pacífico"
            width="1600"
            height="769"
            className={`h-20 w-auto object-contain flex-1 ${collapsed ? 'md:hidden' : ''}`}
          />
          <button
            ref={botonCerrarRef}
            onClick={cerrarMenu}
            className={`shrink-0 w-8 h-8 flex items-center justify-center rounded-lg bg-white/10 border border-white/20 text-white hover:bg-white/20 transition ${
              collapsed ? 'md:hidden' : ''
            }`}
            title="Ocultar menú"
            aria-label={esMovil ? 'Cerrar menú' : 'Ocultar menú'}
          >
            <span className="hidden md:block">
              <PanelLeftClose size={18} />
            </span>
            <span className="md:hidden">
              <X size={18} />
            </span>
          </button>
          <button
            onClick={() => setCollapsed(false)}
            className={`hidden w-8 h-8 shrink-0 items-center justify-center rounded-lg bg-white/10 border border-white/20 text-white hover:bg-white/20 transition ${
              collapsed ? 'md:flex' : ''
            }`}
            title="Mostrar menú"
            aria-label="Mostrar menú"
          >
            <PanelLeftOpen size={18} />
          </button>
        </div>

        {/* NAV - CON SCROLL */}
        <nav className="flex-1 overflow-y-auto p-3 space-y-1 scrollbar-thin">
          {itemsNav.map(({ to, label, icon: Icon, badge }) => (
            <NavLink
              key={to}
              to={to}
              title={label}
              onClick={() => setMenuMovilAbierto(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
                  collapsed ? 'md:justify-center md:px-0' : ''
                } ${
                  isActive
                    ? 'bg-brand-600 text-white shadow-sm'
                    : 'text-white/70 hover:bg-white/10 hover:text-white'
                }`
              }
            >
              <Icon size={18} className="shrink-0" />
              <span className={collapsed ? 'md:hidden' : ''}>{label}</span>
              {badge != null && badge > 0 && (
                <span
                  className={`ml-auto min-w-5 rounded-full bg-amber-400/90 px-1.5 py-0.5 text-center text-[11px] font-bold text-slate-900 ${
                    collapsed ? 'md:hidden' : ''
                  }`}
                  aria-label={`${badge} casos pendientes del comité`}
                >
                  {badge}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        {/* ROL + LOGOUT - FIJO ABAJO, SIEMPRE VISIBLE */}
        <div className="shrink-0 p-3 border-t border-white/10 space-y-2">
          <button
            type="button"
            onClick={() =>
              guardarRol(rol === 'asesor' ? 'administrador' : 'asesor')
            }
            title={`Vista actual: ${rol === 'asesor' ? 'Asesor' : 'Administrador'} — alternar rol`}
            className={`w-full flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium text-white/70 hover:bg-white/10 hover:text-white transition ${
              collapsed ? 'md:justify-center md:px-0' : ''
            }`}
          >
            {rol === 'asesor' ? (
              <UserCog size={18} className="shrink-0" />
            ) : (
              <ShieldCheck size={18} className="shrink-0" />
            )}
            <span
              className={`flex-1 text-left ${collapsed ? 'md:hidden' : ''}`}
            >
              Vista: {rol === 'asesor' ? 'Asesor' : 'Administrador'}
            </span>
            <span
              className={`text-[10px] uppercase tracking-wide text-white/40 ${
                collapsed ? 'md:hidden' : ''
              }`}
            >
              cambiar
            </span>
          </button>
          <button
            onClick={() => {
              setMenuMovilAbierto(false)
              onLogout()
            }}
            title="Cerrar sesión"
            className={`w-full flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-white/70 hover:bg-white/10 hover:text-white transition ${
              collapsed ? 'md:justify-center md:px-0' : ''
            }`}
          >
            <LogOut size={18} className="shrink-0" />
            <span className={collapsed ? 'md:hidden' : ''}>Cerrar sesión</span>
          </button>
        </div>
      </aside>
    </>
  )
}
