import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import PrivateRoute from './components/PrivateRoute';
import Layout from './components/Layout';
import Login from './pages/Login';
import CallsList from './pages/CallsList';
import CallDetail from './pages/CallDetail';
import ClientsList from './pages/ClientsList';
import ClientDetail from './pages/ClientDetail';
import Dashboard from './pages/Dashboard';
import Analytics from './pages/Analytics';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />

          {/* Private routes wrapped in Layout */}
          <Route element={<PrivateRoute />}>
            <Route element={<Layout />}>
              <Route path="/" element={<Navigate to="/calls" replace />} />
              <Route path="/calls" element={<CallsList />} />
              <Route path="/calls/:id" element={<CallDetail />} />
              <Route path="/clients" element={<ClientsList />} />
              <Route path="/clients/:id" element={<ClientDetail />} />
            </Route>
          </Route>

          {/* Dashboard & Analytics: chief/admin only */}
          <Route element={<PrivateRoute allowedRoles={['chief', 'admin']} />}>
            <Route element={<Layout />}>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/analytics" element={<Analytics />} />
            </Route>
          </Route>

          {/* Catch-all */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

