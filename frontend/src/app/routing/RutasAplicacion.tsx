import { Routes, Route, Navigate } from 'react-router-dom'
import type { ReactNode } from 'react'
import ContenedorPanel from '../../widgets/app-shell/ContenedorPanel'
import IniciarSesion from '../../pages/IniciarSesion'
import Resumen from '../../pages/Resumen'
import NuevaSolicitud from '../../pages/NuevaSolicitud'
import Solicitudes from '../../pages/Solicitudes'
import DetalleSolicitud from '../../pages/DetalleSolicitud'
import Originacion from '../../pages/Originacion'
import Clientes from '../../pages/Clientes'
import Riesgo from '../../pages/Riesgo'
import Estados from '../../pages/Estados'
import Ajustes from '../../pages/Ajustes'

function RequireAuth({ children }: { children: ReactNode }) {
  const authed = localStorage.getItem('uw_auth') === '1'
  return authed ? children : <Navigate to="/login" replace />
}

export default function RutasAplicacion() {
  return (
    <Routes>
      <Route path="/login" element={<IniciarSesion />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <ContenedorPanel />
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Resumen />} />
        <Route path="nueva-simulacion" element={<NuevaSolicitud />} />
        <Route path="originacion" element={<Originacion />} />
        <Route path="solicitudes" element={<Solicitudes />} />
        <Route path="solicitudes/:id" element={<DetalleSolicitud />} />
        <Route path="clientes" element={<Clientes />} />
        <Route path="riesgo" element={<Riesgo />} />
        <Route path="estados" element={<Estados />} />
        <Route path="ajustes" element={<Ajustes />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
