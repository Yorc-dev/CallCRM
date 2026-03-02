import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

interface PrivateRouteProps {
  allowedRoles?: string[];
}

export default function PrivateRoute({ allowedRoles }: PrivateRouteProps) {
  const { isAuthenticated, user } = useAuth();

  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (allowedRoles && user && !allowedRoles.includes(user.role)) {
    return <Navigate to="/calls" replace />;
  }

  return <Outlet />;
}
