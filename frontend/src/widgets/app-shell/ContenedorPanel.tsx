import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Suspense, useEffect, useState } from 'react'
import BarraLateral from './BarraLateral'
import CargandoPagina from '../../shared/ui/CargandoPagina'
import { tituloPagina } from '../../shared/lib/marca'
import { cerrarSesionApi } from '../../features/auth/api/autenticacionApi'
import { limpiarSesion, obtenerRefresh } from '../../shared/lib/sesion'

export default function ContenedorPanel() {
  const navigate = useNavigate()
  const location = useLocation()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

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
        onLogout={() => {
          // Revoca el refresh en servidor (logout efectivo, D125); la
          // limpieza local no espera la respuesta.
          void cerrarSesionApi(obtenerRefresh())
          limpiarSesion()
          navigate('/login')
        }}
      />
      <div className="flex-1 flex flex-col min-w-0">
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
