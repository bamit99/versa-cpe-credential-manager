import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Row,
  Space,
  Tag,
  Typography,
  message,
} from "antd";
import { ApiOutlined, ReloadOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import api, { errorMessage } from "../../services/api";
import { IntegrationStatus } from "../../types";

function StatusTag({ ok, okText, badText }: { ok: boolean; okText: string; badText: string }) {
  return <Tag color={ok ? "green" : "red"}>{ok ? okText : badText}</Tag>;
}

export default function IntegrationsPage() {
  const [status, setStatus] = useState<IntegrationStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStatus = async (): Promise<void> => {
    setLoading(true);
    try {
      const resp = await api.get<IntegrationStatus>("/admin/integrations");
      setStatus(resp.data);
    } catch (err) {
      message.error(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchStatus();
  }, []);

  return (
    <div>
      <Space style={{ width: "100%", justifyContent: "space-between", marginBottom: 16 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          Integrations
        </Typography.Title>
        <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void fetchStatus()}>
          Refresh
        </Button>
      </Space>

      <Alert
        style={{ marginBottom: 24 }}
        type="info"
        showIcon
        message="Read-only view"
        description="This page reports how external dependencies are wired. LDAP/AD federation and identity-provider settings are changed in the Keycloak Admin Console; secret-store and Director credentials come from environment configuration."
      />

      {status && (
        <Row gutter={[16, 16]}>
          <Col xs={24} lg={12}>
            <Card
              title={
                <Space>
                  <ApiOutlined />
                  Identity provider (Keycloak)
                </Space>
              }
              extra={
                <StatusTag
                  ok={status.keycloak.reachable}
                  okText="Reachable"
                  badText="Unreachable"
                />
              }
              loading={loading}
            >
              <Descriptions column={1} size="small">
                <Descriptions.Item label="Realm">{status.keycloak.realm}</Descriptions.Item>
                <Descriptions.Item label="Issuer">{status.keycloak.issuer}</Descriptions.Item>
                {status.keycloak.detail && (
                  <Descriptions.Item label="Detail">{status.keycloak.detail}</Descriptions.Item>
                )}
              </Descriptions>
              <Button
                type="link"
                style={{ paddingLeft: 0 }}
                href={status.keycloak.console_url}
                target="_blank"
                rel="noreferrer"
              >
                Open Keycloak Admin Console
              </Button>
            </Card>
          </Col>

          <Col xs={24} lg={12}>
            <Card
              title="LDAP / Active Directory federation"
              extra={
                status.ldap.configured === null ? (
                  <Tag color="orange">Unknown</Tag>
                ) : (
                  <StatusTag
                    ok={status.ldap.configured}
                    okText="Configured"
                    badText="Not configured"
                  />
                )
              }
              loading={loading}
            >
              <Descriptions column={1} size="small">
                {status.ldap.provider_names.length > 0 && (
                  <Descriptions.Item label="Providers">
                    {status.ldap.provider_names.join(", ")}
                  </Descriptions.Item>
                )}
                {status.ldap.connection_url && (
                  <Descriptions.Item label="Connection">
                    {status.ldap.connection_url}
                  </Descriptions.Item>
                )}
                {status.ldap.edit_mode && (
                  <Descriptions.Item label="Edit mode">{status.ldap.edit_mode}</Descriptions.Item>
                )}
                {status.ldap.enabled !== null && (
                  <Descriptions.Item label="Enabled">
                    {status.ldap.enabled ? "Yes" : "No"}
                  </Descriptions.Item>
                )}
                {status.ldap.detail && (
                  <Descriptions.Item label="Detail">{status.ldap.detail}</Descriptions.Item>
                )}
              </Descriptions>
            </Card>
          </Col>

          <Col xs={24} lg={8}>
            <Card
              title="Secret store"
              extra={
                <StatusTag
                  ok={status.secret_store.healthy}
                  okText="Healthy"
                  badText="Unavailable"
                />
              }
              loading={loading}
            >
              <Descriptions column={1} size="small">
                <Descriptions.Item label="Backend">{status.secret_store.backend}</Descriptions.Item>
                <Descriptions.Item label="Detail">{status.secret_store.detail}</Descriptions.Item>
              </Descriptions>
            </Card>
          </Col>

          <Col xs={24} lg={8}>
            <Card
              title="Director API credentials"
              extra={
                <Tag color={status.director_creds.mock_mode ? "orange" : "green"}>
                  {status.director_creds.mock_mode ? "Mock (dev)" : "Live"}
                </Tag>
              }
              loading={loading}
            >
              <Descriptions column={1} size="small">
                <Descriptions.Item label="Directors">
                  {status.director_creds.directors_count}
                </Descriptions.Item>
                <Descriptions.Item label="API username">
                  {status.director_creds.api_username_configured ? "Set" : "Not set"}
                </Descriptions.Item>
                <Descriptions.Item label="Detail">{status.director_creds.detail}</Descriptions.Item>
              </Descriptions>
            </Card>
          </Col>

          <Col xs={24} lg={8}>
            <Card
              title="Break-glass access"
              extra={
                <StatusTag
                  ok={status.break_glass.admin_count > 0}
                  okText="Available"
                  badText="No admin"
                />
              }
              loading={loading}
            >
              <Descriptions column={1} size="small">
                <Descriptions.Item label="Local users">
                  {status.break_glass.local_user_count}
                </Descriptions.Item>
                <Descriptions.Item label="Local admins">
                  {status.break_glass.admin_count}
                </Descriptions.Item>
                <Descriptions.Item label="Guidance">
                  {status.break_glass.guidance}
                </Descriptions.Item>
              </Descriptions>
            </Card>
          </Col>
        </Row>
      )}
    </div>
  );
}
