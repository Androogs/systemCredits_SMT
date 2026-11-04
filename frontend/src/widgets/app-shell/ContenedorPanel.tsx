import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Suspense, useEffect, useRef, useState } from 'react'
import { Menu } from 'lucide-react'
import BarraLateral from './BarraLateral'
import CargandoPagina from '../../shared/ui/CargandoPagina'
import { MARCA, tituloPagina } from '../../shared/lib/marca'
import { cerrarSesionApi } from '../../features/auth/api/autenticacionApi'
import { limpiarSesion, obtenerRefresh } from '../../shared/lib/sesion'

export default function ContenedorPanel() {
  const navigate = useNavigate()
  const location = useLocation()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const botonMenuRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const heading = document.querySelector<HTMLElement>('#main-content h1')
    const title = heading?.textContent?.trim()
    if (!heading || !title) return

    document.title = tituloPagina(title)
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
          // Revoca el refresh en servidor (logout efectivo, D125); la
          // limpieza local no espera la respuesta.
          void cerrarSesionApi(obtenerRefresh())
          limpiarSesion()
          navigate('/login')
        }}
      />
      <div className="flex-1 flex flex-col min-w-0">
        <header className="md:hidden sticky top-0 z-30 flex items-center gap-3 border-b border-slate-200 bg-white/95 px-4 py-2.5 backdrop-blur">
          <button
            ref={botonMenuRef}
            onClick={() => setMobileMenuOpen(true)}
            className="p-2 rounded-lg bg-brand-900 border border-white/20 text-white shadow-sm"
            title="Abrir menú"
            aria-label="Abrir menú"
            aria-haspopup="dialog"
            aria-expanded={mobileMenuOpen}
            aria-controls="sidebar-nav"
            tabIndex={mobileMenuOpen ? -1 : 0}
          >
            <Menu size={20} />
          </button>
          <img
            src={MARCA.logoClaro}
            alt={MARCA.razonSocial}
            width="900"
            height="129"
            className="h-5 w-auto object-contain"
          />
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
