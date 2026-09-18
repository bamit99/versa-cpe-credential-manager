import { useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { Spin } from "antd";
import { useAuthStore } from "./store/authStore";
import ProtectedRoute from "./components/auth/ProtectedRoute";
import MainLayout from "./components/layout/MainLayout";
import LoginPage from "./pages/login/Login";
import DashboardPage from "./pages/dashboard/index";
import InventoryPage from "./pages/cpe/Inventory";
import DetailPage from "./pages/cpe/Detail";
import AuditPage from "./pages/audit/Logs";
import RotationPage from "./pages/rotation/index";
import SettingsPage from "./pages/admin/Settings";
import DirectorsPage from "./pages/admin/Directors";
import AssignmentsPage from "./pages/admin/Assignments";
import UsersPage from "./pages/admin/Users";
import IntegrationsPage from "./pages/admin/Integrations";

export default function App() {
  const { initialised, authenticated, init } = useAuthStore();

  useEffect(() => {
    void init();
  }, [init]);

  if (!initialised) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh" }}>
        <Spin size="large" tip="Initialising..." />
      </div>
    );
  }

  if (!authenticated) {
    return <LoginPage />;
  }

  return (
    <ProtectedRoute>
      <Routes>
        <Route element={<MainLayout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/cpe" element={<InventoryPage />} />
          <Route path="/cpe/:cpeId" element={<DetailPage />} />
          <Route
            path="/rotation"
            element={
              <ProtectedRoute roles={["security_operator", "admin"]}>
                <RotationPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/audit"
            element={
              <ProtectedRoute roles={["security_operator", "admin"]}>
                <AuditPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/settings"
            element={
              <ProtectedRoute roles={["admin"]}>
                <SettingsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/directors"
            element={
              <ProtectedRoute roles={["admin"]}>
                <DirectorsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/assignments"
            element={
              <ProtectedRoute roles={["admin"]}>
                <AssignmentsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/users"
            element={
              <ProtectedRoute roles={["admin"]}>
                <UsersPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/integrations"
            element={
              <ProtectedRoute roles={["admin"]}>
                <IntegrationsPage />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Routes>
    </ProtectedRoute>
  );
}