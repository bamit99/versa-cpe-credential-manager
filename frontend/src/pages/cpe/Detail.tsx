import {
  Card,
  Descriptions,
  Tag,
  Typography,
  Space,
  Button,
  Modal,
  Form,
  Input,
  message,
  Alert,
  InputNumber,
  Divider,
} from "antd";
import { EyeOutlined, ReloadOutlined, ArrowLeftOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import api, { errorMessage } from "../../services/api";
import { CPE, CredentialMeta, CredentialReveal } from "../../types";
import { getRoles } from "../../services/keycloak";

const STATUS_COLOR: Record<string, string> = {
  online: "green",
  offline: "red",
  unknown: "default",
};

export default function DetailPage() {
  const { cpeId } = useParams<{ cpeId: string }>();
  const navigate = useNavigate();
  const [cpe, setCpe] = useState<CPE | null>(null);
  const [cred, setCred] = useState<CredentialMeta | null>(null);
  const [revealOpen, setRevealOpen] = useState(false);
  const [revealed, setRevealed] = useState<CredentialReveal | null>(null);
  const [revealLoading, setRevealLoading] = useState(false);
  const [rotateLoading, setRotateLoading] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const roles = getRoles();

  const load = async (): Promise<void> => {
    const resp = await api.get<CPE>(`/cpes/${cpeId}`);
    setCpe(resp.data);
    const credResp = await api.get<CredentialMeta>(`/cpes/${cpeId}/credential`).catch(() => null);
    if (credResp) setCred(credResp.data);
  };

  useEffect(() => {
    void load().catch((err) => {
      message.error(errorMessage(err));
      navigate("/cpe");
    });
  }, [cpeId]);

  useEffect(() => {
    if (countdown <= 0) {
      setRevealed(null);
      return;
    }
    const t = window.setTimeout(() => setCountdown((c) => c - 1), 1000);
    return () => window.clearTimeout(t);
  }, [countdown]);

  const reveal = async (values: { reason: string; ticket_reference?: string }) => {
    setRevealLoading(true);
    try {
      const resp = await api.post<CredentialReveal>(`/cpes/${cpeId}/reveal`, values);
      setRevealed(resp.data);
      setCountdown(resp.data.display_timeout_seconds);
      setRevealOpen(false);
      message.success("Credential revealed (hidden automatically after timeout)");
      void load();
    } catch (err) {
      message.error(errorMessage(err));
    } finally {
      setRevealLoading(false);
    }
  };

  const rotate = async () => {
    setRotateLoading(true);
    try {
      await api.post(`/cpes/${cpeId}/rotate`);
      message.success("Rotation completed");
      void load();
    } catch (err) {
      message.error(errorMessage(err));
    } finally {
      setRotateLoading(false);
    }
  };

  if (!cpe) return null;

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/cpe")}>
          Inventory
        </Button>
        <Typography.Title level={3} style={{ margin: 0 }}>
          {cpe.cpe_id}
        </Typography.Title>
        <Tag color={STATUS_COLOR[cpe.status]}>{cpe.status}</Tag>
      </Space>

      <Card title="CPE Identity" style={{ marginBottom: 16 }}>
        <Descriptions column={{ xs: 1, md: 2, lg: 3 }} bordered size="small">
          <Descriptions.Item label="Device Name">{cpe.device_name ?? "—"}</Descriptions.Item>
          <Descriptions.Item label="Serial Number">{cpe.serial_number ?? "—"}</Descriptions.Item>
          <Descriptions.Item label="Site">{cpe.site ?? "—"}</Descriptions.Item>
          <Descriptions.Item label="Management IP">{cpe.management_ip ?? "—"}</Descriptions.Item>
          <Descriptions.Item label="Director">{cpe.director_id ?? "—"}</Descriptions.Item>
          <Descriptions.Item label="Last Seen">{cpe.last_seen_at ?? "—"}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="Credential">
        <Descriptions column={1} bordered size="small">
          <Descriptions.Item label="Username">{cred?.username ?? "—"}</Descriptions.Item>
          <Descriptions.Item label="Version">{cred?.version ?? "—"}</Descriptions.Item>
          <Descriptions.Item label="Status">
            {cred?.status ? <Tag>{cred.status}</Tag> : "—"}
          </Descriptions.Item>
          <Descriptions.Item label="Last Rotation">{cred?.last_rotated_at ?? "—"}</Descriptions.Item>
          <Descriptions.Item label="Last Access">{cred?.last_accessed_at ?? "—"}</Descriptions.Item>
        </Descriptions>

        <Divider />

        {revealed ? (
          <Alert
            type="warning"
            message={
              <Space direction="vertical">
                <span>
                  Secret visible for <strong>{countdown}s</strong> — it is never stored in your browser.
                </span>
                <Typography.Text copyable={{ text: revealed.password }} style={{ fontSize: 16 }}>
                  {revealed.password}
                </Typography.Text>
              </Space>
            }
            action={
              <Button size="small" onClick={() => setRevealed(null)}>
                Hide now
              </Button>
            }
            showIcon
          />
        ) : (
          <Space>
            <Button type="primary" icon={<EyeOutlined />} onClick={() => setRevealOpen(true)}>
              Request credential access
            </Button>
            {roles.some((r) => ["security_operator", "admin"].includes(r)) && (
              <Button icon={<ReloadOutlined />} loading={rotateLoading} onClick={rotate}>
                Rotate credential
              </Button>
            )}
          </Space>
        )}
      </Card>

      <Modal
        title={`Request credential access — ${cpeId}`}
        open={revealOpen}
        onCancel={() => setRevealOpen(false)}
        footer={null}
      >
        <Form layout="vertical" onFinish={reveal}>
          <Form.Item
            name="reason"
            label="Reason"
            rules={[{ required: true, min: 4, message: "A reason is required" }]}
          >
            <Input.TextArea rows={3} placeholder="e.g. On-site troubleshooting at site ..." />
          </Form.Item>
          <Form.Item name="ticket_reference" label="Ticket / Reference">
            <Input placeholder="e.g. INC-12345" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={revealLoading} block>
              Reveal credential
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}