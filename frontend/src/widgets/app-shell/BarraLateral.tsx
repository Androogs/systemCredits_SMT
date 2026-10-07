import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import type { LucideIcon } from 'lucide-react'
import {
  LayoutDashboard,
  FilePlus2,
  ListChecks,
  LogOut,
  Users,
  ShieldAlert,
  ActivityIcon,
  Settings2,
  PanelLeftClose,
  PanelLeftOpen,
  Briefcase,
  Calculator,
  Menu,
  X,
} from 'lucide-react'

const nav: { to: string; label: string; icon: LucideIcon }[] = [
  { to: '/dashboard', label: 'Resumen', icon: LayoutDashboard },
  { to: '/asesor', label: 'Panel asesor', icon: Briefcase },
  { to: '/solicitudes', label: 'Solicitudes', icon: ListChecks },
  { to: '/nueva-solicitud', label: 'Nueva solicitud', icon: FilePlus2 },
  { to: '/simulador', label: 'Simulador', icon: Calculator },
  { to: '/clientes', label: 'Clientes', icon: Users },
  { to: '/riesgo', label: 'Riesgo', icon: ShieldAlert },
  { to: '/estados', label: 'Estados', icon: ActivityIcon },
  { to: '/ajustes', label: 'Administración', icon: Settings2 },
]

export default function BarraLateral({ onLogout }: { onLogout: () => void }) {
  const [collapsed, setCollapsed] = useState(false)
  const [menuMovilAbierto, setMenuMovilAbierto] = useState(false)

  const cerrarMenu = () => {
    if (window.matchMedia('(max-width: 767.98px)').matches) {
      setMenuMovilAbierto(false)
    } else {
      setCollapsed(true)
    }
  }

  return (
    <>
      {/* BOTÓN HAMBURGUESA - SOLO MÓVIL */}
      <button
        onClick={() => setMenuMovilAbierto(true)}
        className={`
          md:hidden fixed top-4 left-4 z-40 p-2.5 rounded-xl
          bg-[rgba(0,0,51,1)] border border-white/20 text-white shadow-lg
          transition-all duration-300 ease-in-out
          ${menuMovilAbierto ? 'opacity-0 -translate-x-10 scale-90 pointer-events-none' : 'opacity-100 translate-x-0 scale-100'}
        `}
        title="Abrir menú"
        aria-label="Abrir menú"
      >
        <Menu size={20} />
      </button>

      {/* BACKDROP - SOLO MÓVIL */}
      <button
        aria-label="Cerrar menú"
        onClick={() => setMenuMovilAbierto(false)}
        className={`
          md:hidden fixed inset-0 z-40 bg-black/50 backdrop-blur-sm
          transition-opacity duration-300
          ${menuMovilAbierto ? 'opacity-100' : 'opacity-0 pointer-events-none'}
        `}
      />

      <aside
        className={`
        fixed md:sticky inset-y-0 left-0 top-0 z-50 md:z-auto
        flex flex-col border-r border-white/10 bg-[rgba(0,0,51,1)]
        h-screen w-64 shrink-0
        transition-all duration-300 ease-in-out
        ${menuMovilAbierto ? 'translate-x-0' : '-translate-x-full'}
        ${
          collapsed
            ? 'md:w-0 md:-translate-x-full md:opacity-0 md:overflow-hidden'
            : 'md:w-64 md:translate-x-0 md:opacity-100'
        }
      `}
      >
        {/* HEADER - FIJO */}
        <div className="flex items-center h-20 border-b border-white/10 px-4 gap-2 min-w-[16rem] shrink-0">
          <img
            src="/brand/pacifico-blancos.png"
            alt="Inversiones Pacífico"
            className="h-20 w-auto object-contain flex-1"
          />
          <button
            onClick={cerrarMenu}
            className="shrink-0 w-8 h-8 flex items-center justify-center rounded-lg bg-white/10 border border-white/20 text-white hover:bg-white/20 transition"
            title="Ocultar menú"
            aria-label="Ocultar menú"
          >
            <span className="hidden md:block">
              <PanelLeftClose size={18} />
            </span>
            <span className="md:hidden">
              <X size={18} />
            </span>
          </button>
        </div>

        {/* NAV - CON SCROLL */}
        <nav className="flex-1 overflow-y-auto p-3 space-y-1 min-w-[16rem] scrollbar-thin">
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              onClick={() => setMenuMovilAbierto(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
                  isActive
                    ? 'bg-brand-600 text-white shadow-sm'
                    : 'text-white/70 hover:bg-white/10 hover:text-white'
                }`
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* LOGOUT - FIJO ABAJO, SIEMPRE VISIBLE */}
        <div className="shrink-0 p-3 border-t border-white/10 min-w-[16rem]">
          <button
            onClick={() => {
              setMenuMovilAbierto(false)
              onLogout()
            }}
            className="w-full flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-white/70 hover:bg-white/10 hover:text-white transition"
          >
            <LogOut size={18} /> Cerrar sesión
          </button>
        </div>
      </aside>

      {/* BOTÓN FLOTANTE CUANDO ESTÁ OCULTO - SOLO DESKTOP */}
      <button
        onClick={() => setCollapsed(false)}
        className={`
          hidden md:flex fixed top-4 left-4 z-50 p-2.5 rounded-xl
          bg-[rgba(0,0,51,1)] border border-white/20 text-white shadow-lg
          transition-all duration-300 ease-in-out
          ${collapsed ? 'opacity-100 translate-x-0 scale-100' : 'opacity-0 -translate-x-10 scale-90 pointer-events-none'}
        `}
        title="Mostrar menú"
      >
        <PanelLeftOpen size={20} />
      </button>
    </>
  )
}
