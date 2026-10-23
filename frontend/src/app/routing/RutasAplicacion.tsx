import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import type { ReactNode } from 'react'
import ContenedorPanel from '../../widgets/app-shell/ContenedorPanel'
import IniciarSesion from '../../pages/IniciarSesion'
import CargandoPagina from '../../shared/ui/CargandoPagina'
import {
  haySesionVigente,
  obtenerRol,
  obtenerUsuario,
} from '../../shared/lib/sesion'
import type { RolSesion } from '../../shared/lib/sesion'

// Las páginas viajan en chunks por ruta: el asesor en la vitrina solo
// descarga la pantalla que usa, no el panel completo (bundle inicial).
const CapturaMovil = lazy(() => import('../../pages/CapturaMovil'))
const VerificarFirma = lazy(() => import('../../pages/VerificarFirma'))
const RecuperarClave = lazy(() => import('../../pages/RecuperarClave'))
const RestablecerClave = lazy(() => import('../../pages/RestablecerClave'))
const Resumen = lazy(() => import('../../pages/Resumen'))
const Simulador = lazy(() => import('../../pages/Simulador'))
const Solicitudes = lazy(() => import('../../pages/Solicitudes'))
const DetalleSolicitud = lazy(() => import('../../pages/DetalleSolicitud'))
const Resultado = lazy(() => import('../../pages/Resultado'))
const Originacion = lazy(() => import('../../pages/Originacion'))
const Clientes = lazy(() => import('../../pages/Clientes'))
const Riesgo = lazy(() => import('../../pages/Riesgo'))
const Estados = lazy(() => import('../../pages/Estados'))
const Ajustes = lazy(() => import('../../pages/Ajustes'))

function RequireAuth({ children }: { children: ReactNode }) {
  const { pathname } = useLocation()
  if (!haySesionVigente()) return <Navigate to="/login" replace />
  // Clave temporal entregada por el admin: el usuario no opera el panel
  // hasta definir su propia contraseña.
  if (obtenerUsuario()?.requiere_cambio_password && pathname !== '/ajustes') {
    return <Navigate to="/ajustes" replace />
  }
  return children
}

/** Guard de rol: complemento visual de la autorización del backend.
 * Un rol sin permiso recibe 403 de la API igualmente; aquí solo se
 * evita mostrar la pantalla. */
function RequireRol({
  roles,
  children,
}: {
  roles: RolSesion[]
  children: ReactNode
}) {
  return roles.includes(obtenerRol()) ? (
    children
  ) : (
    <Navigate to="/dashboard" replace />
  )
}

export default function RutasAplicacion() {
  return (
    <Routes>
      <Route path="/login" element={<IniciarSesion />} />
      {/* Recuperación de clave (D124): públicas — el token del correo
          es la credencial del paso 2, sin sesión. */}
      <Route
        path="/recuperar-clave"
        element={
          <Suspense fallback={<CargandoPagina />}>
            <RecuperarClave />
          </Suspense>
        }
      />
      <Route
        path="/restablecer-clave"
        element={
          <Suspense fallback={<CargandoPagina />}>
            <RestablecerClave />
          </Suspense>
        }
      />
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
        {/* Flujo operativo (radicar, simular, panel del asesor):
            admin y asesor; el aliado solo consulta. */}
        {/* El panel del asesor se fusionó en /dashboard: la ruta vieja
            queda como redirect para enlaces guardados. */}
        <Route path="asesor" element={<Navigate to="/dashboard" replace />} />
        <Route
          path="nueva-solicitud"
          element={
            <RequireRol roles={['admin', 'asesor', 'concesionario']}>
              <Originacion />
            </RequireRol>
          }
        />
        <Route
          path="originacion"
          element={<Navigate to="/nueva-solicitud" replace />}
        />
        <Route
          path="nueva-simulacion"
          element={<Navigate to="/simulador" replace />}
        />
        <Route
          path="simulador"
          element={
            <RequireRol roles={['admin', 'asesor', 'concesionario']}>
              <Simulador />
            </RequireRol>
          }
        />
        <Route path="solicitudes" element={<Solicitudes />} />
        <Route path="solicitudes/:id" element={<DetalleSolicitud />} />
        <Route path="solicitudes/:id/resultado" element={<Resultado />} />
        <Route
          path="clientes"
          element={
            <RequireRol roles={['admin', 'asesor', 'concesionario']}>
              <Clientes />
            </RequireRol>
          }
        />
        {/* Analítica del motor y configuración: expediente interno,
            solo administrador. */}
        <Route
          path="riesgo"
          element={
            <RequireRol roles={['admin']}>
              <Riesgo />
            </RequireRol>
          }
        />
        <Route
          path="estados"
          element={
            <RequireRol roles={['admin']}>
              <Estados />
            </RequireRol>
          }
        />
        {/* Ajustes para todos los roles: la página misma restringe las
            secciones por rol (no-admin solo ve Cuenta). */}
        <Route path="ajustes" element={<Ajustes />} />
        {/* El cambio de clave vive en Ajustes > Cuenta; la ruta vieja
            queda como redirect para enlaces guardados. */}
        <Route
          path="cambiar-clave"
          element={<Navigate to="/ajustes" replace />}
        />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
