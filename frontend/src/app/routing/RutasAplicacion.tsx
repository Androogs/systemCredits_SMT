import { Routes, Route, Navigate } from 'react-router-dom'
import type { ReactNode } from 'react'
import ContenedorPanel from '../../widgets/app-shell/ContenedorPanel'
import IniciarSesion from '../../pages/IniciarSesion'
import Resumen from '../../pages/Resumen'
import Simulador from '../../pages/Simulador'
import PanelAsesor from '../../pages/PanelAsesor'
import Solicitudes from '../../pages/Solicitudes'
import DetalleSolicitud from '../../pages/DetalleSolicitud'
import Resultado from '../../pages/Resultado'
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
        <Route path="asesor" element={<PanelAsesor />} />
        <Route path="nueva-solicitud" element={<Originacion />} />
        <Route
          path="originacion"
          element={<Navigate to="/nueva-solicitud" replace />}
        />
        <Route
          path="nueva-simulacion"
          element={<Navigate to="/simulador" replace />}
        />
        <Route path="simulador" element={<Simulador />} />
        <Route path="solicitudes" element={<Solicitudes />} />
        <Route path="solicitudes/:id" element={<DetalleSolicitud />} />
        <Route path="solicitudes/:id/resultado" element={<Resultado />} />
        <Route path="clientes" element={<Clientes />} />
        <Route path="riesgo" element={<Riesgo />} />
        <Route path="estados" element={<Estados />} />
        <Route path="ajustes" element={<Ajustes />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
