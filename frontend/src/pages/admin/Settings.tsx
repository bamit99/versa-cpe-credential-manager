import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  InputNumber,
  Row,
  Space,
  Typography,
  message,
} from "antd";
import { SaveOutlined } from "@ant-design/icons";
import { useEffect, useMemo, useState } from "react";
import api, { errorMessage } from "../../services/api";
import { PasswordPolicy } from "../../types";

const FIELD_META: { key: keyof PasswordPolicy; label: string; hint: string }[] = [
  { key: "length", label: "Total length", hint: "Password length (12–128)" },
  { key: "min_lower", label: "Min lowercase", hint: "Minimum lowercase letters" },
  { key: "min_upper", label: "Min uppercase", hint: "Minimum uppercase letters" },
  { key: "min_digit", label: "Min digits", hint: "Minimum digits" },
  { key: "min_special", label: "Min special", hint: "Minimum special characters" },
];

export default function SettingsPage() {
  const [form] = Form.useForm<PasswordPolicy>();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState<PasswordPolicy | null>(null);

  const values = Form.useWatch([], form) as PasswordPolicy | undefined;
  const minTotal = useMemo(() => {
    if (!values) return 0;
    return (
      (values.min_lower ?? 0) +
      (values.min_upper ?? 0) +
      (values.min_digit ?? 0) +
      (values.min_special ?? 0)
    );
  }, [values]);

  const impossible = !!values && values.length < minTotal;

  const fetchPolicy = async (): Promise<void> => {
    setLoading(true);
    try {
      const resp = await api.get<PasswordPolicy>("/admin/password-policy");
      form.setFieldsValue(resp.data);
      setLastSaved(resp.data);
    } catch (err) {
      message.error(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchPolicy();
  }, []);

  const save = async (): Promise<void> => {
    const body = await form.validateFields();
    if (body.length < minTotal) {
      message.error(
        "Impossible policy: sum of character-class minimums exceeds total length.",
      );
      return;
    }
    setSaving(true);
    try {
      const resp = await api.put<PasswordPolicy>("/admin/password-policy", body);
      form.setFieldsValue(resp.data);
      setLastSaved(resp.data);
      message.success("Password policy updated.");
    } catch (err) {
      message.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const reset = (): void => {
    if (lastSaved) form.setFieldsValue(lastSaved);
    else void fetchPolicy();
  };

  return (
    <div>
      <Typography.Title level={3} style={{ marginTop: 0 }}>
        Admin Settings
      </Typography.Title>

      <Card title="Credential generation policy" loading={loading}>
        <Alert
          style={{ marginBottom: 24 }}
          type="info"
          showIcon
          message="Applies to newly generated and every rotated credential."
          description="Saved here, the policy is applied at generation time (credential creation and rotation). Increasing minimums will not rewrite existing secrets."
        />

        <Form form={form} layout="horizontal" labelCol={{ span: 7 }} wrapperCol={{ span: 8 }}>
          <Row gutter={16}>
            {FIELD_META.map(({ key, label, hint }) => (
              <Col xs={24} sm={12} lg={8} key={key}>
                <Form.Item
                  name={key}
                  label={label}
                  rules={[
                    { required: true, message: "Required" },
                    {
                      type: "number",
                      min: key === "length" ? 12 : 0,
                      max: 128,
                      message: "Out of range",
                    },
                  ]}
                  extra={hint}
                >
                  <InputNumber min={key === "length" ? 12 : 0} max={128} style={{ width: "100%" }} />
                </Form.Item>
              </Col>
            ))}
          </Row>

          {impossible && (
            <Alert
              style={{ marginBottom: 16 }}
              type="error"
              showIcon
              message={`Minimums sum to ${minTotal}, which exceeds the total length ${values?.length}.`}
            />
          )}

          <Space>
            <Button type="primary" icon={<SaveOutlined />} loading={saving} disabled={impossible} onClick={() => void save()}>
              Save policy
            </Button>
            <Button onClick={reset}>Discard changes</Button>
          </Space>
        </Form>
      </Card>
    </div>
  );
}