import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import {
  DeleteOutlined,
  DownloadOutlined,
  PlusOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { useEffect, useState } from "react";
import api, { errorMessage } from "../../services/api";
import { CPEListResponse, Director, DirectorStatus, SyncCpesResult } from "../../types";

const VERSION_OPTIONS = [
  { label: "22.1.3", value: "22.1.3" },
  { label: "22.1.4", value: "22.1.4" },
];

export default function DirectorsPage() {
  const [rows, setRows] = useState<Director[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();
  const [probeResults, setProbeResults] = useState<Record<number, DirectorStatus>>({});
  const [probeLoading, setProbeLoading] = useState<Record<number, boolean>>({});
  const [pulling, setPulling] = useState<Record<number, boolean>>({});
  const [pullResult, setPullResult] = useState<{ director: string; result: SyncCpesResult } | null>(
    null,
  );
  const [cpeCounts, setCpeCounts] = useState<Record<number, number>>({});

  const fetchDirectors = async (): Promise<void> => {
    setLoading(true);
    try {
      const resp = await api.get<Director[]>("/admin/directors");
      setRows(resp.data);
    } catch (err) {
      message.error(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const fetchCpeCounts = async (directors: Director[]): Promise<void> => {
    const entries = await Promise.all(
      directors.map(async (d) => {
        try {
          const resp = await api.get<CPEListResponse>("/cpes", {
            params: { director_id: d.id, page_size: 1 },
          });
          return [d.id, resp.data.total] as const;
        } catch {
          return [d.id, 0] as const;
        }
      }),
    );
    setCpeCounts(Object.fromEntries(entries));
  };

  useEffect(() => {
    void fetchDirectors();
  }, []);

  useEffect(() => {
    if (rows.length > 0) void fetchCpeCounts(rows);
  }, [rows]);

  const pullCpes = async (d: Director): Promise<void> => {
    setPulling((s) => ({ ...s, [d.id]: true }));
    try {
      const resp = await api.post<SyncCpesResult>(`/admin/directors/${d.id}/sync-cpes`);
      setPullResult({ director: d.name, result: resp.data });
      message.success(
        `${d.name}: pulled ${resp.data.discovered} CPEs (${resp.data.created} new, ${resp.data.updated} updated).`,
      );
      void fetchCpeCounts(rows);
    } catch (err) {
      message.error(errorMessage(err));
    } finally {
      setPulling((s) => ({ ...s, [d.id]: false }));
    }
  };

  const probe = async (d: Director): Promise<void> => {
    setProbeLoading((s) => ({ ...s, [d.id]: true }));
    try {
      const resp = await api.get<DirectorStatus>(`/admin/directors/${d.id}/status`);
      setProbeResults((s) => ({ ...s, [d.id]: resp.data }));
    } catch (err) {
      message.error(errorMessage(err));
    } finally {
      setProbeLoading((s) => ({ ...s, [d.id]: false }));
    }
  };

  const toggleEnabled = async (d: Director, enabled: boolean): Promise<void> => {
    try {
      await api.put<Director>(`/admin/directors/${d.id}`, { enabled });
      message.success(`${d.name} ${enabled ? "enabled" : "disabled"}.`);
      void fetchDirectors();
    } catch (err) {
      message.error(errorMessage(err));
    }
  };

  const createDirector = async (): Promise<void> => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      await api.post("/admin/directors", values);
      message.success("Director added.");
      setModalOpen(false);
      form.resetFields();
      void fetchDirectors();
    } catch (err) {
      message.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const removeDirector = async (d: Director): Promise<void> => {
    try {
      await api.delete(`/admin/directors/${d.id}`);
      message.success(`Deleted ${d.name}.`);
      void fetchDirectors();
    } catch (err) {
      message.error(errorMessage(err));
    }
  };

  return (
    <div>
      <Space style={{ width: "100%", justifyContent: "space-between", marginBottom: 16 }} wrap>
        <Typography.Title level={3} style={{ margin: 0 }}>
          Versa Directors
        </Typography.Title>
        <Space wrap>
          <Button icon={<ReloadOutlined />} onClick={() => void fetchDirectors()}>
            Refresh
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
            Add Director
          </Button>
        </Space>
      </Space>

      {pullResult && (
        <Alert
          style={{ marginBottom: 16 }}
          type="success"
          showIcon
          message={`Pulled ${pullResult.result.discovered} CPEs from ${pullResult.director}`}
          description={`${pullResult.result.created} created, ${pullResult.result.updated} updated in local inventory.`}
          closable
          onClose={() => setPullResult(null)}
        />
      )}

      <Card>
        <Table<Director>
          rowKey="id"
          loading={loading}
          dataSource={rows}
          columns={[
            { title: "Name", dataIndex: "name" },
            { title: "Host", dataIndex: "host" },
            {
              title: "Version",
              dataIndex: "versa_version",
              render: (v: string) => <Tag color="blue">{v}</Tag>,
            },
            {
              title: "Capabilities",
              dataIndex: "capabilities",
              render: (caps: Record<string, boolean>, d: Director) => {
                const list = Object.entries(caps).filter(([, ok]) => ok);
                if (list.length === 0) return <Typography.Text type="secondary">—</Typography.Text>;
                return list.map(([k]) => <Tag key={k}>{k}</Tag>);
              },
            },
            {
              title: "Enabled",
              dataIndex: "enabled",
              render: (enabled: boolean, d: Director) => (
                <Switch checked={enabled} onChange={(v) => void toggleEnabled(d, v)} />
              ),
            },
            {
              title: "CPEs",
              key: "cpe_count",
              render: (_: unknown, d: Director) =>
                cpeCounts[d.id] !== undefined ? <Tag>{cpeCounts[d.id]}</Tag> : "—",
            },
            {
              title: "Reachability",
              key: "status",
              render: (_: unknown, d: Director) => {
                const r = probeResults[d.id];
                return (
                  <Space>
                    <Button
                      size="small"
                      icon={<ThunderboltOutlined />}
                      loading={probeLoading[d.id]}
                      onClick={() => void probe(d)}
                    >
                      Probe
                    </Button>
                    {r && (
                      <Tag color={r.reachable ? "green" : "red"}>
                        {r.reachable ? `OK ${r.latency_ms}ms` : "unreachable"}
                      </Tag>
                    )}
                  </Space>
                );
              },
            },
            {
              title: "Actions",
              key: "actions",
              render: (_: unknown, d: Director) => (
                <Space>
                  <Button
                    size="small"
                    type="primary"
                    ghost
                    icon={<DownloadOutlined />}
                    loading={pulling[d.id]}
                    onClick={() => void pullCpes(d)}
                  >
                    Pull CPEs
                  </Button>
                  <Popconfirm title={`Delete ${d.name}?`} onConfirm={() => void removeDirector(d)}>
                    <Button danger size="small" icon={<DeleteOutlined />} />
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
          pagination={false}
        />
      </Card>

      <Modal
        title="Add Director"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => void createDirector()}
        confirmLoading={saving}
        destroyOnHidden
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="Name" rules={[{ required: true, message: "Required" }]}>
            <Input placeholder="VD-EU-2214" />
          </Form.Item>
          <Form.Item name="host" label="Host" rules={[{ required: true, message: "Required" }]}>
            <Input placeholder="director.example.com" />
          </Form.Item>
          <Form.Item
            name="api_base_url"
            label="API Base URL"
            rules={[{ required: true, message: "Required" }]}
          >
            <Input placeholder="https://director.example.com:9183" />
          </Form.Item>
          <Form.Item
            name="versa_version"
            label="Versa Version"
            rules={[{ required: true, message: "Required" }]}
          >
            <Select options={VERSION_OPTIONS} />
          </Form.Item>
          <Form.Item
            name="oauth_client_id"
            label="OAuth Client ID"
            rules={[{ required: true, message: "Required" }]}
          >
            <Input placeholder="cpe-manager" />
          </Form.Item>
          <Form.Item name="oauth_secret_ref" label="OAuth Secret Reference">
            <Input placeholder="secret:director-eu-2214" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}