import { Button, Card, Typography, Space, Alert } from "antd";
import { SafetyCertificateOutlined, LoginOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import { useAuthStore } from "../../store/authStore";

export default function LoginPage() {
  const { authenticated, initialised, signIn } = useAuthStore();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialised && authenticated) {
      window.location.href = "/dashboard";
    }
  }, [initialised, authenticated]);

  const handleLogin = async () => {
    setError(null);
    try {
      await signIn();
    } catch {
      setError("Unable to contact the identity provider. Is Keycloak running?");
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(135deg, #001529 0%, #1677ff 100%)",
      }}
    >
      <Card style={{ width: 380, textAlign: "center" }} variant="outlined">
        <Space direction="vertical" size="middle" style={{ width: "100%" }}>
          <SafetyCertificateOutlined style={{ fontSize: 48, color: "#1677ff" }} />
          <Typography.Title level={4} style={{ marginBottom: 0 }}>
            Versa CPE Credential Manager
          </Typography.Title>
          <Typography.Paragraph type="secondary">
            Sign in with your corporate identity (LDAP / SSO via Keycloak)
          </Typography.Paragraph>
          {error && <Alert type="error" showIcon message={error} />}
          <Button type="primary" size="large" block icon={<LoginOutlined />} onClick={handleLogin}>
            Sign in
          </Button>
        </Space>
      </Card>
    </div>
  );
}