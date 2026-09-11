import { Table, Input, Tag, Button, Space, Typography, Upload, message, Select } from "antd";
import { SearchOutlined, ReloadOutlined, UploadOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { errorMessage } from "../../services/api";
import { CPE, CPEListResponse } from "../../types";

const STATUS_COLOR: Record<string, string> = {
  online: "green",
  offline: "red",
  unknown: "default",
};

export default function InventoryPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<CPEListResponse>({ items: [], total: 0, page: 1, page_size: 50 });
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<string>("");

  const fetchData = async (page = 1) => {
    setLoading(true);
    try {
      const resp = await api.get<CPEListResponse>("/cpes", {
        params: { search, status: status || undefined, page, page_size: 50 },
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
  }, [status]);

  const importCsv = async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    try {
      const resp = await api.post<{ created: number; updated: number }>("/cpes/import", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      message.success(`Imported: ${resp.data.created} created, ${resp.data.updated} updated`);
      void fetchData(1);
    } catch (err) {
      message.error(errorMessage(err));
    }
    return false;
  };

  const columns = [
    { title: "CPE ID", dataIndex: "cpe_id", key: "cpe_id" },
    { title: "Device Name", dataIndex: "device_name", key: "device_name" },
    { title: "Serial", dataIndex: "serial_number", key: "serial_number" },
    { title: "Site", dataIndex: "site", key: "site" },
    { title: "Mgmt IP", dataIndex: "management_ip", key: "management_ip" },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      render: (v: string) => <Tag color={STATUS_COLOR[v]}>{v}</Tag>,
    },
    {
      title: "Action",
      key: "action",
      render: (_: unknown, row: CPE) => (
        <Button type="link" onClick={() => navigate(`/cpe/${row.cpe_id}`)}>
          Details
        </Button>
      ),
    },
  ];

  return (
    <div>
      <Space style={{ width: "100%", justifyContent: "space-between", marginBottom: 16 }} wrap>
        <Typography.Title level={3} style={{ margin: 0 }}>
          CPE Inventory
        </Typography.Title>
        <Space wrap>
          <Input
            placeholder="Search ID / name / serial / site / IP"
            prefix={<SearchOutlined />}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onPressEnter={() => void fetchData(1)}
            allowClear
            style={{ width: 320 }}
          />
          <Select
            placeholder="Status"
            value={status || undefined}
            onChange={setStatus}
            style={{ width: 140 }}
            options={[
              { value: "online", label: "Online" },
              { value: "offline", label: "Offline" },
              { value: "unknown", label: "Unknown" },
            ]}
            allowClear
          />
          <Button icon={<ReloadOutlined />} onClick={() => void fetchData(1)}>
            Refresh
          </Button>
          <Upload accept=".csv" beforeUpload={importCsv} showUploadList={false}>
            <Button icon={<UploadOutlined />}>Import CSV</Button>
          </Upload>
        </Space>
      </Space>
      <Table<CPE>
        rowKey="id"
        loading={loading}
        columns={columns}
        dataSource={data.items}
        pagination={{
          current: data.page,
          total: data.total,
          pageSize: data.page_size,
          showSizeChanger: false,
          showTotal: (t) => `${t} CPEs`,
          onChange: (page) => void fetchData(page),
        }}
        onRow={(row) => ({ onClick: () => navigate(`/cpe/${row.cpe_id}`), style: { cursor: "pointer" } })}
      />
    </div>
  );
}