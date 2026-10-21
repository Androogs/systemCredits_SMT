import { Routes, Route, Navigate } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import type { ReactNode } from 'react'
import ContenedorPanel from '../../widgets/app-shell/ContenedorPanel'
import IniciarSesion from '../../pages/IniciarSesion'
import CargandoPagina from '../../shared/ui/CargandoPagina'

// Las páginas viajan en chunks por ruta: el asesor en la vitrina solo
// descarga la pantalla que usa, no el panel completo (bundle inicial).
const CapturaMovil = lazy(() => import('../../pages/CapturaMovil'))
const VerificarFirma = lazy(() => import('../../pages/VerificarFirma'))
const Resumen = lazy(() => import('../../pages/Resumen'))
const Simulador = lazy(() => import('../../pages/Simulador'))
const PanelAsesor = lazy(() => import('../../pages/PanelAsesor'))
const Solicitudes = lazy(() => import('../../pages/Solicitudes'))
const DetalleSolicitud = lazy(() => import('../../pages/DetalleSolicitud'))
const Resultado = lazy(() => import('../../pages/Resultado'))
const Originacion = lazy(() => import('../../pages/Originacion'))
const Clientes = lazy(() => import('../../pages/Clientes'))
const Riesgo = lazy(() => import('../../pages/Riesgo'))
const Estados = lazy(() => import('../../pages/Estados'))
const Ajustes = lazy(() => import('../../pages/Ajustes'))

function RequireAuth({ children }: { children: ReactNode }) {
  const authed = localStorage.getItem('uw_auth') === '1'
  return authed ? children : <Navigate to="/login" replace />
}

export default function RutasAplicacion() {
  return (
    <Routes>
      <Route path="/login" element={<IniciarSesion />} />
      {/* Captura remota de evidencias: el token del link es la única
          autorización; el cliente no necesita sesión del asesor. */}
      <Route
        path="/captura/:token"
        element={
          <Suspense fallback={<CargandoPagina />}>
            <CapturaMovil />
          </Suspense>
        }
      />
      {/* Verificación pública de firma: destino del QR estampado en los
          documentos de legalización; no requiere sesión. */}
      <Route
        path="/verificar-firma/:uuid"
        element={
          <Suspense fallback={<CargandoPagina />}>
            <VerificarFirma />
          </Suspense>
        }
      />
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
