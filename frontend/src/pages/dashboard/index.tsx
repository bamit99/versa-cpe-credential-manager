import { Card, Col, Row, Statistic, Typography } from "antd";
import {
  ClusterOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  EyeOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { useEffect, useState } from "react";
import api from "../../services/api";
import { DashboardStats } from "../../types";

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);

  useEffect(() => {
    void api.get<DashboardStats>("/dashboard").then((r) => setStats(r.data));
  }, []);

  return (
    <div>
      <Typography.Title level={3}>Dashboard</Typography.Title>
      <Row gutter={[16, 16]}>
        <Col xs={12} md={6}>
          <Card>
            <Statistic title="Total CPEs" value={stats?.total_cpes ?? 0} prefix={<ClusterOutlined />} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card>
            <Statistic
              title="Online"
              value={stats?.online_cpes ?? 0}
              valueStyle={{ color: "#3f8600" }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card>
            <Statistic
              title="Offline"
              value={stats?.offline_cpes ?? 0}
              valueStyle={{ color: "#cf1322" }}
              prefix={<CloseCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card>
            <Statistic
              title="Needs Rotation"
              value={stats?.credentials_needing_rotation ?? 0}
              valueStyle={{ color: "#d48806" }}
              prefix={<WarningOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic
              title="Recent Rotation Failures (7d)"
              value={stats?.rotation_failures_recent ?? 0}
              prefix={<SyncOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic
              title="Recent Privileged Access (7d)"
              value={stats?.recent_privileged_access ?? 0}
              prefix={<EyeOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic
              title="Recent Rotations (7d)"
              value={stats?.recent_rotations ?? 0}
              prefix={<SyncOutlined />}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}