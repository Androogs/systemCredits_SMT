import { Routes, Route, Navigate } from 'react-router-dom';
import DashboardLayout from '../../widgets/app-shell/DashboardLayout';
import Login from '../../pages/Login';
import Dashboard from '../../pages/Dashboard';
import NewApplication from '../../pages/NewApplication';
import Applications from '../../pages/Applications';
import ApplicationDetail from '../../pages/ApplicationDetail';
import Originacion from '../../pages/Originacion';
import Clientes from '../../pages/Clientes';
import Riesgo from '../../pages/Riesgo';
import Estados from '../../pages/Estados';
import Ajustes from '../../pages/Ajustes';

function RequireAuth({ children }) {
  const authed = localStorage.getItem('uw_auth') === '1';
  return authed ? children : <Navigate to="/login" replace />;
}

export default function UnderwritingRoutes() {
  return (
    <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<RequireAuth><DashboardLayout /></RequireAuth>}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="nueva-simulacion" element={<NewApplication />} />
          <Route path="originacion" element={<Originacion />} />
          <Route path="solicitudes" element={<Applications />} />
          <Route path="solicitudes/:id" element={<ApplicationDetail />} />
          <Route path="clientes" element={<Clientes />} />
          <Route path="riesgo" element={<Riesgo />} />
          <Route path="estados" element={<Estados />} />
          <Route path="ajustes" element={<Ajustes />} />
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
