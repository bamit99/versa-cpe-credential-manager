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
          <Route path="/audit" element={<AuditPage />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Routes>
    </ProtectedRoute>
  );
}