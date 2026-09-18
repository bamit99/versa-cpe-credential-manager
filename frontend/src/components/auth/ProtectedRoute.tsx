import { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuthStore } from "../../store/authStore";

export default function ProtectedRoute({
  children,
  roles,
}: {
  children: ReactNode;
  roles?: string[];
}) {
  const authenticated = useAuthStore((s) => s.authenticated);
  const userRoles = useAuthStore((s) => s.roles);
  const location = useLocation();

  if (!authenticated) {
    return <Navigate to="/" replace state={{ from: location.pathname }} />;
  }
  if (roles && roles.length > 0 && !roles.some((r) => userRoles.includes(r))) {
    return <Navigate to="/dashboard" replace />;
  }
  return <>{children}</>;
}