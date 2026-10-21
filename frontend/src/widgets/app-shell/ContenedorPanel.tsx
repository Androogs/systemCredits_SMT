import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Suspense, useEffect, useRef, useState } from 'react'
import { Menu } from 'lucide-react'
import BarraLateral from './BarraLateral'
import CargandoPagina from '../../shared/ui/CargandoPagina'

export default function ContenedorPanel() {
  const navigate = useNavigate()
  const location = useLocation()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const botonMenuRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const heading = document.querySelector<HTMLElement>('#main-content h1')
    const title = heading?.textContent?.trim()
    if (!heading || !title) return

    document.title = `${title} | Inversiones Pacífico`
    heading.tabIndex = -1
    heading.focus({ preventScroll: true })
  }, [location.pathname])

  return (
    <div className="min-h-screen flex bg-slate-50">
      <a className="skip-link" href="#main-content">
        Saltar al contenido principal
      </a>
      <BarraLateral
        mobileMenuOpen={mobileMenuOpen}
        onMobileMenuChange={setMobileMenuOpen}
        botonMenuRef={botonMenuRef}
        onLogout={() => {
          localStorage.removeItem('uw_auth')
          navigate('/login')
        }}
      />
      <div className="flex-1 flex flex-col min-w-0">
        <header className="md:hidden sticky top-0 z-30 flex items-center gap-3 border-b border-slate-200 bg-white/95 px-4 py-2.5 backdrop-blur">
          <button
            ref={botonMenuRef}
            onClick={() => setMobileMenuOpen(true)}
            className="p-2 rounded-lg bg-[rgba(0,0,51,1)] border border-white/20 text-white shadow-sm"
            title="Abrir menú"
            aria-label="Abrir menú"
            aria-haspopup="dialog"
            aria-expanded={mobileMenuOpen}
            aria-controls="sidebar-nav"
            tabIndex={mobileMenuOpen ? -1 : 0}
          >
            <Menu size={20} />
          </button>
          <span className="text-sm font-semibold tracking-tight text-slate-800">
            Inversiones Pacífico
          </span>
        </header>
        <main
          key={location.pathname}
          className="route-enter flex min-h-0 flex-1 flex-col"
          id="main-content"
          tabIndex={-1}
          inert={mobileMenuOpen}
        >
          <Suspense fallback={<CargandoPagina />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  )
}
