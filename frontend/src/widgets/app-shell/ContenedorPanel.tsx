import { Outlet, useNavigate } from 'react-router-dom'
import BarraLateral from './BarraLateral'

export default function ContenedorPanel() {
  const navigate = useNavigate()
  return (
    <div className="min-h-screen flex bg-slate-50">
      <BarraLateral
        onLogout={() => {
          localStorage.removeItem('uw_auth')
          navigate('/login')
        }}
      />
      <div className="flex-1 flex flex-col min-w-0">
        <Outlet />
      </div>
    </div>
  )
}
