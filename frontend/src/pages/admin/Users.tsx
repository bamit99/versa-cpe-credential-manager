import {
  Alert,
  Button,
  Card,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import { CloudSyncOutlined, ReloadOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import api, { errorMessage } from "../../services/api";
import { AdminUser, IdentitySyncResult } from "../../types";

const ROLE_COLOR: Record<string, string> = {
  admin: "purple",
  security_operator: "blue",
  field_engineer: "green",
};

export default function UsersPage() {
  const [rows, setRows] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<IdentitySyncResult | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);

  const fetchUsers = async (): Promise<void> => {
    setLoading(true);
    try {
      const resp = await api.get<AdminUser[]>("/admin/users");
      setRows(resp.data);
    } catch (err) {
      message.error(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchUsers();
  }, []);

  const sync = async (): Promise<void> => {
    setSyncing(true);
    setSyncResult(null);
    setSyncError(null);
    try {
      const resp = await api.post<IdentitySyncResult>("/admin/sync/users");
      setSyncResult(resp.data);
      message.success(`Synced ${resp.data.total} users from Keycloak.`);
      void fetchUsers();
    } catch (err) {
      const msg = errorMessage(err);
      setSyncError(msg);
      message.error(msg);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div>
      <Space style={{ width: "100%", justifyContent: "space-between", marginBottom: 16 }} wrap>
        <Typography.Title level={3} style={{ margin: 0 }}>
          Users
        </Typography.Title>
        <Space wrap>
          <Button icon={<ReloadOutlined />} onClick={() => void fetchUsers()}>
            Refresh
          </Button>
          <Button
            type="primary"
            icon={<CloudSyncOutlined />}
            loading={syncing}
            onClick={() => void sync()}
          >
            Sync from Keycloak
          </Button>
        </Space>
      </Space>

      {syncResult && (
        <Alert
          style={{ marginBottom: 16 }}
          type="success"
          showIcon
          message={`Keycloak sync complete: ${syncResult.created} created, ${syncResult.updated} updated (${syncResult.total} users seen).`}
          closable
          onClose={() => setSyncResult(null)}
        />
      )}
      {syncError && (
        <Alert
          style={{ marginBottom: 16 }}
          type="error"
          showIcon
          message={`Sync failed: ${syncError}`}
          description="Check the Keycloak admin client credentials and that the service account can read realm users."
          closable
          onClose={() => setSyncError(null)}
        />
      )}

      <Card>
        <Table<AdminUser>
          rowKey="subject"
          loading={loading}
          dataSource={rows}
          columns={[
            { title: "Username", dataIndex: "username" },
            { title: "Email", dataIndex: "email", render: (v: string | null) => v ?? "—" },
            { title: "Name", key: "name", render: (_: unknown, u: AdminUser) => [u.first_name, u.last_name].filter(Boolean).join(" ") || "—" },
            {
              title: "Roles",
              dataIndex: "roles",
              render: (roles: string[]) => (
                <>
                  {roles.length === 0 ? <Typography.Text type="secondary">—</Typography.Text> : null}
                  {roles.map((r) => (
                    <Tag key={r} color={ROLE_COLOR[r]}>
                      {r}
                    </Tag>
                  ))}
                </>
              ),
            },
            {
              title: "Enabled",
              dataIndex: "enabled",
              render: (v: boolean) =>
                v ? <Tag color="green">enabled</Tag> : <Tag color="red">disabled</Tag>,
            },
            {
              title: "Last login",
              dataIndex: "last_login_at",
              render: (v: string | null) =>
                v ? new Date(v).toLocaleString() : "—",
            },
          ]}
          pagination={{ pageSize: 20, showTotal: (t) => `${t} users` }}
        />
      </Card>
    </div>
  );
}