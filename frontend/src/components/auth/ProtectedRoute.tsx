import { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuthStore } from "../../store/authStore";

export default function ProtectedRoute({ children }: { children: ReactNode }) {
  const authenticated = useAuthStore((s) => s.authenticated);
  const location = useLocation();

  if (!authenticated) {
    return <Navigate to="/" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}