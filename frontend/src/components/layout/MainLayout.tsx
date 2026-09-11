import { Layout, Menu, Avatar, Dropdown, Space, Typography } from "antd";
import {
  DashboardOutlined,
  ClusterOutlined,
  AuditOutlined,
  LogoutOutlined,
  SafetyCertificateOutlined,
} from "@ant-design/icons";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { useAuthStore } from "../../store/authStore";
import { getRoles } from "../../services/keycloak";

const { Sider, Header, Content } = Layout;

export default function MainLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const signOut = useAuthStore((s) => s.signOut);
  const roles = getRoles();

  const menuItems = [
    { key: "/dashboard", icon: <DashboardOutlined />, label: "Dashboard" },
    { key: "/cpe", icon: <ClusterOutlined />, label: "CPE Inventory" },
    roles.includes("security_operator") || roles.includes("admin")
      ? { key: "/audit", icon: <AuditOutlined />, label: "Audit Log" }
      : null,
  ].filter(Boolean) as { key: string; icon: React.ReactNode; label: string }[];

  const selectedKey = "/" + (location.pathname.split("/")[1] || "dashboard");

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider breakpoint="lg" collapsedWidth={0} theme="dark">
        <div style={{ padding: 16, color: "#fff", display: "flex", alignItems: "center", gap: 8 }}>
          <SafetyCertificateOutlined style={{ fontSize: 22 }} />
          <div>
            <Typography.Text strong style={{ color: "#fff", display: "block" }}>
              Versa CPE
            </Typography.Text>
            <Typography.Text type="secondary" style={{ color: "#aaa", fontSize: 12 }}>
              Credential Manager
            </Typography.Text>
          </div>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: "#fff",
            padding: "0 24px",
            display: "flex",
            justifyContent: "flex-end",
            alignItems: "center",
            boxShadow: "0 1px 4px rgba(0,21,41,.08)",
          }}
        >
          <Dropdown
            menu={{
              items: [{ key: "logout", icon: <LogoutOutlined />, label: "Sign out", onClick: signOut }],
            }}
          >
            <Space style={{ cursor: "pointer" }}>
              <Avatar size="small" style={{ background: "#1677ff" }}>
                {(useAuthStore.getState().roles.length
                  ? useAuthStore.getState().roles[0][0]
                  : "U")?.toUpperCase()}
              </Avatar>
              <Typography.Text>{roles.join(", ")}</Typography.Text>
            </Space>
          </Dropdown>
        </Header>
        <Content style={{ margin: 24 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}