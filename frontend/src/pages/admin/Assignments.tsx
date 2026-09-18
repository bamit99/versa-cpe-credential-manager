import { Button, Card, Input, Select, Space, Table, Tag, Typography, message } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { useEffect, useMemo, useState } from "react";
import api, { errorMessage } from "../../services/api";
import { AdminUser, Assignment, CPE, CPEListResponse } from "../../types";

export default function AssignmentsPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [selectedSubject, setSelectedSubject] = useState<string | null>(null);
  const [cpes, setCpes] = useState<CPE[]>([]);
  const [total, setTotal] = useState(0);
  const [assignedIds, setAssignedIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [search, setSearch] = useState("");

  const loadUsers = async (): Promise<void> => {
    try {
      const resp = await api.get<AdminUser[]>("/admin/users");
      const list = resp.data.filter((u) => u.roles.includes("field_engineer"));
      setUsers(list);
      setSelectedSubject(null);
    } catch (err) {
      message.error(errorMessage(err));
    }
  };

  const loadCpes = async (): Promise<void> => {
    setLoading(true);
    try {
      const resp = await api.get<CPEListResponse>("/cpes", {
        params: { page: 1, page_size: 500 },
      });
      setCpes(resp.data.items);
      setTotal(resp.data.total);
    } catch (err) {
      message.error(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const loadAssignments = async (subject: string): Promise<void> => {
    try {
      const resp = await api.get<Assignment[]>("/admin/assignments", {
        params: { user_subject: subject },
      });
      setAssignedIds(new Set(resp.data.map((a) => a.cpe_id)));
    } catch (err) {
      message.error(errorMessage(err));
    }
  };

  useEffect(() => {
    void loadUsers();
    void loadCpes();
  }, []);

  useEffect(() => {
    if (selectedSubject) void loadAssignments(selectedSubject);
    else setAssignedIds(new Set());
  }, [selectedSubject]);

  const toggle = async (cpe: CPE, assign: boolean): Promise<void> => {
    if (!selectedSubject) return;
    setToggling(true);
    try {
      if (assign) {
        await api.post("/admin/assignments", { user_subject: selectedSubject, cpe_id: cpe.cpe_id });
      } else {
        await api.delete("/admin/assignments", { data: { user_subject: selectedSubject, cpe_id: cpe.cpe_id } });
      }
      setAssignedIds((prev) => {
        const next = new Set(prev);
        if (assign) next.add(cpe.cpe_id);
        else next.delete(cpe.cpe_id);
        return next;
      });
      message.success(`${cpe.cpe_id} ${assign ? "assigned" : "unassigned"}.`);
    } catch (err) {
      message.error(errorMessage(err));
    } finally {
      setToggling(false);
    }
  };

  const rows = useMemo(() => {
    if (!search.trim()) return cpes;
    const q = search.trim().toLowerCase();
    return cpes.filter(
      (c) =>
        c.cpe_id.toLowerCase().includes(q) ||
        (c.device_name ?? "").toLowerCase().includes(q) ||
        (c.site ?? "").toLowerCase().includes(q),
    );
  }, [cpes, search]);

  const selectedUsername = users.find((u) => u.subject === selectedSubject)?.username;

  return (
    <div>
      <Space style={{ width: "100%", justifyContent: "space-between", marginBottom: 16 }} wrap>
        <Typography.Title level={3} style={{ margin: 0 }}>
          CPE Assignments
        </Typography.Title>
        <Space wrap>
          <Input.Search
            placeholder="Filter CPEs…"
            allowClear
            style={{ width: 240 }}
            onSearch={setSearch}
          />
          <Button
            icon={<ReloadOutlined />}
            onClick={() => {
              void loadUsers();
              void loadCpes();
            }}
          >
            Refresh
          </Button>
        </Space>
      </Space>

      <Card style={{ marginBottom: 16 }}>
        <Typography.Text strong style={{ marginRight: 12 }}>
          Field engineer:
        </Typography.Text>
        <Select
          style={{ width: 320 }}
          placeholder="Select a field engineer…"
          value={selectedSubject}
          onChange={setSelectedSubject}
          options={users.map((u) => ({
            value: u.subject,
            label: `${u.username}${u.email ? ` (${u.email})` : ""}`,
          }))}
        />
        {selectedSubject && (
          <Tag style={{ marginLeft: 12 }} color="blue">
            {assignedIds.size} assigned of {total} CPEs
          </Tag>
        )}
      </Card>

      <Card>
        <Table<CPE>
          rowKey="cpe_id"
          loading={loading}
          dataSource={rows}
          size="small"
          columns={[
            { title: "CPE ID", dataIndex: "cpe_id" },
            { title: "Device Name", dataIndex: "device_name", render: (v: string | null) => v ?? "—" },
            { title: "Site", dataIndex: "site", render: (v: string | null) => v ?? "—" },
            {
              title: "Status",
              dataIndex: "status",
              render: (v: string) => (
                <Tag color={v === "online" ? "green" : v === "offline" ? "red" : "default"}>{v}</Tag>
              ),
            },
            {
              title: "Assigned",
              key: "assigned",
              render: (_: unknown, cpe: CPE) => {
                if (!selectedSubject) {
                  return (
                    <Typography.Text type="secondary">—</Typography.Text>
                  );
                }
                const isAssigned = assignedIds.has(cpe.cpe_id);
                return (
                  <Button
                    size="small"
                    type={isAssigned ? "primary" : "default"}
                    loading={toggling}
                    onClick={() => void toggle(cpe, !isAssigned)}
                  >
                    {isAssigned ? "Assigned" : "Assign"}
                  </Button>
                );
              },
            },
          ]}
          pagination={{ pageSize: 20, showTotal: (t) => `${t} shown` }}
        />
        {!selectedSubject && (
          <Typography.Text type="secondary">
            Select a field engineer to manage their CPE assignments ({total} total CPEs).
          </Typography.Text>
        )}
      </Card>
    </div>
  );
}