import { Card, Table, Tag, Typography, Space, Select, Input, message } from "antd";
import { useEffect, useState } from "react";
import api, { errorMessage } from "../../services/api";
import { AuditEvent, AuditLogResponse } from "../../types";

const ACTION_COLOR: Record<string, string> = {
  CREDENTIAL_VIEW_REQUESTED: "blue",
  CREDENTIAL_VIEWED: "cyan",
  CREDENTIAL_GENERATED: "geekblue",
  CREDENTIAL_ROTATION_REQUESTED: "purple",
  CREDENTIAL_ROTATION_STARTED: "purple",
  CREDENTIAL_ROTATION_SUCCEEDED: "green",
  CREDENTIAL_ROTATION_FAILED: "red",
  CPE_IMPORTED: "orange",
  CPE_UPDATED: "orange",
  ACCESS_DENIED: "red",
};

export default function AuditPage() {
  const [data, setData] = useState<AuditLogResponse>({ items: [], total: 0, page: 1, page_size: 100 });
  const [loading, setLoading] = useState(false);
  const [action, setAction] = useState<string>("");
  const [cpeId, setCpeId] = useState<string>("");

  const fetchData = async (page = 1) => {
    setLoading(true);
    try {
      const resp = await api.get<AuditLogResponse>("/audit", {
        params: { action: action || undefined, cpe_id: cpeId || undefined, page, page_size: 100 },
      });
      setData(resp.data);
    } catch (err) {
      message.error(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchData(1);
  }, [action, cpeId]);

  const columns = [
    {
      title: "Timestamp",
      dataIndex: "timestamp",
      key: "timestamp",
      render: (v: string) => new Date(v).toLocaleString(),
    },
    { title: "User", dataIndex: "user_username", key: "user_username" },
    {
      title: "Action",
      dataIndex: "action",
      key: "action",
      render: (v: string) => <Tag color={ACTION_COLOR[v] ?? "default"}>{v}</Tag>,
    },
    { title: "CPE", dataIndex: "cpe_id", key: "cpe_id" },
    { title: "Ticket", dataIndex: "ticket_reference", key: "ticket_reference" },
    { title: "IP", dataIndex: "source_ip", key: "source_ip" },
    {
      title: "Result",
      dataIndex: "success",
      key: "success",
      render: (v: boolean) => (v ? <Tag color="green">OK</Tag> : <Tag color="red">FAILED</Tag>),
    },
    { title: "Correlation ID", dataIndex: "correlation_id", key: "correlation_id" },
  ];

  return (
    <div>
      <Card
        title={<Typography.Title level={3} style={{ margin: 0 }}>Audit Log</Typography.Title>}
        style={{ marginBottom: 16 }}
      >
        <Space>
          <Select
            placeholder="Action"
            value={action || undefined}
            onChange={setAction}
            allowClear
            style={{ width: 260 }}
            options={Object.keys(ACTION_COLOR).map((a) => ({ value: a, label: a }))}
          />
          <Input
            placeholder="Filter by CPE ID"
            value={cpeId}
            onChange={(e) => setCpeId(e.target.value)}
            style={{ width: 220 }}
            allowClear
          />
        </Space>
      </Card>
      <Table<AuditEvent>
        rowKey="id"
        loading={loading}
        columns={columns}
        dataSource={data.items}
        pagination={{
          current: data.page,
          total: data.total,
          pageSize: data.page_size,
          showSizeChanger: false,
          onChange: (page) => void fetchData(page),
        }}
      />
    </div>
  );
}