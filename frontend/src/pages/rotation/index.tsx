import {
  Alert,
  Button,
  Card,
  Segmented,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import { ReloadOutlined, SyncOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { errorMessage } from "../../services/api";
import {
  AuditEvent,
  AuditLogResponse,
  BulkRotateResponse,
  CPE,
  CPEListResponse,
} from "../../types";

const STATUS_COLOR: Record<string, string> = {
  online: "green",
  offline: "red",
  unknown: "default",
};

const ROTATION_ACTIONS = ["CREDENTIAL_ROTATION_SUCCEEDED", "CREDENTIAL_ROTATION_FAILED"];

export default function RotationPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<CPEListResponse>({ items: [], total: 0, page: 1, page_size: 100 });
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<React.Key[]>([]);
  const [scope, setScope] = useState<"due" | "all">("due");
  const [rotating, setRotating] = useState(false);
  const [result, setResult] = useState<BulkRotateResponse | null>(null);
  const [activity, setActivity] = useState<AuditEvent[]>([]);
  const [activityLoading, setActivityLoading] = useState(false);

  const fetchCpes = async (page = 1): Promise<void> => {
    setLoading(true);
    try {
      const resp = await api.get<CPEListResponse>("/cpes", {
        params: {
          page,
          page_size: 100,
          needs_rotation: scope === "due" || undefined,
          sort_by: "cpe_id",
        },
      });
      setData(resp.data);
    } catch (err) {
      message.error(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const fetchActivity = async (): Promise<void> => {
    setActivityLoading(true);
    try {
      const calls = ROTATION_ACTIONS.map((action) =>
        api.get<AuditLogResponse>("/audit", { params: { action, page_size: 50 } }),
      );
      const [ok, failed] = await Promise.all(calls);
      const merged: AuditEvent[] = [...ok.data.items, ...failed.data.items]
        .sort((a, b) => (a.timestamp < b.timestamp ? 1 : -1))
        .slice(0, 20);
      setActivity(merged);
    } catch (err) {
      message.error(errorMessage(err));
    } finally {
      setActivityLoading(false);
    }
  };

  useEffect(() => {
    void fetchCpes(1);
    setSelected([]);
  }, [scope]);

  useEffect(() => {
    void fetchActivity();
  }, []);

  const rotateSelected = async (): Promise<void> => {
    if (selected.length === 0) return;
    setRotating(true);
    setResult(null);
    try {
      const resp = await api.post<BulkRotateResponse>("/bulk/rotate", selected.map(String));
      const okCount = resp.data.results.filter((r) => r.ok).length;
      setResult(resp.data);
      message.success(`${okCount}/${resp.data.results.length} rotated`);
      setSelected([]);
      void fetchCpes(data.page);
      void fetchActivity();
    } catch (err) {
      message.error(errorMessage(err));
    } finally {
      setRotating(false);
    }
  };

  const columns = [
    { title: "CPE ID", dataIndex: "cpe_id", key: "cpe_id" },
    { title: "Device Name", dataIndex: "device_name", key: "device_name" },
    { title: "Site", dataIndex: "site", key: "site" },
    { title: "Mgmt IP", dataIndex: "management_ip", key: "management_ip" },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      render: (v: string) => <Tag color={STATUS_COLOR[v]}>{v}</Tag>,
    },
  ];

  return (
    <div>
      <Space style={{ width: "100%", justifyContent: "space-between", marginBottom: 16 }} wrap>
        <Typography.Title level={3} style={{ margin: 0 }}>
          Credential Rotation
        </Typography.Title>
        <Space wrap>
          <Segmented
            options={[
              { label: "Due for rotation", value: "due" },
              { label: "All CPEs", value: "all" },
            ]}
            value={scope}
            onChange={(v) => setScope(v as "due" | "all")}
          />
          <Button icon={<ReloadOutlined />} onClick={() => void fetchCpes(data.page)}>
            Refresh
          </Button>
        </Space>
      </Space>

      <Card title="Select CPEs to rotate" style={{ marginBottom: 16 }}>
        <Table<CPE>
          rowKey="cpe_id"
          loading={loading}
          columns={columns}
          dataSource={data.items}
          rowSelection={{ selectedRowKeys: selected, onChange: setSelected }}
          pagination={{
            current: data.page,
            total: data.total,
            pageSize: data.page_size,
            showSizeChanger: false,
            showTotal: (t) => `${t} CPEs`,
            onChange: (page) => void fetchCpes(page),
          }}
          onRow={(row) => ({ onDoubleClick: () => navigate(`/cpe/${row.cpe_id}`) })}
        />
        <Space style={{ marginTop: 16 }}>
          <Button
            type="primary"
            icon={<SyncOutlined />}
            loading={rotating}
            disabled={selected.length === 0}
            onClick={() => void rotateSelected()}
          >
            Rotate selected ({selected.length})
          </Button>
        </Space>

        {result && (
          <Alert
            style={{ marginTop: 16 }}
            type={result.results.every((r) => r.ok) ? "success" : "warning"}
            message={`Bulk rotation: ${result.results.filter((r) => r.ok).length} succeeded, ${result.results.filter((r) => !r.ok).length} failed of ${result.requested} requested`}
            description={
              result.results.some((r) => !r.ok) ? (
                <ul style={{ margin: 0, paddingLeft: 20 }}>
                  {result.results
                    .filter((r) => !r.ok)
                    .map((r) => (
                      <li key={r.cpe_id}>
                        {r.cpe_id}: {r.error ?? "failed"}
                      </li>
                    ))}
                </ul>
              ) : undefined
            }
            showIcon
            closable
            onClose={() => setResult(null)}
          />
        )}
      </Card>

      <Card title="Recent rotation activity" loading={activityLoading}>
        <Table<AuditEvent>
          rowKey="id"
          size="small"
          columns={[
            { title: "Time", dataIndex: "timestamp", key: "timestamp", render: (v: string) => new Date(v).toLocaleString() },
            { title: "CPE", dataIndex: "cpe_id", key: "cpe_id" },
            {
              title: "Action",
              dataIndex: "action",
              key: "action",
              render: (v: string) => (
                <Tag color={v === "CREDENTIAL_ROTATION_SUCCEEDED" ? "green" : "red"}>{v}</Tag>
              ),
            },
            { title: "User", dataIndex: "user_username", key: "user_username" },
            {
              title: "Result",
              dataIndex: "success",
              key: "success",
              render: (v: boolean) => (v ? <Tag color="green">OK</Tag> : <Tag color="red">FAILED</Tag>),
            },
          ]}
          dataSource={activity}
          pagination={false}
        />
      </Card>
    </div>
  );
}