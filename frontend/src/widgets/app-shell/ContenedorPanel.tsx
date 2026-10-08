import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import BarraLateral from './BarraLateral'

export default function ContenedorPanel() {
  const navigate = useNavigate()
  const location = useLocation()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

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
        onMobileMenuChange={setMobileMenuOpen}
        onLogout={() => {
          localStorage.removeItem('uw_auth')
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
          <Outlet />
        </main>
      </div>
    </div>
  )
}
