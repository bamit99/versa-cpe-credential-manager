"""initial schema

Revision ID: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "directors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("api_base_url", sa.String(255), nullable=False),
        sa.Column("versa_version", sa.String(32), nullable=False),
        sa.Column("oauth_client_id", sa.String(255), nullable=False),
        sa.Column("oauth_secret_ref", sa.String(255)),
        sa.Column("capabilities_json", sa.String(2048), server_default="{}", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "cpes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cpe_id", sa.String(128), nullable=False, unique=True),
        sa.Column("device_name", sa.String(255)),
        sa.Column("serial_number", sa.String(255)),
        sa.Column("site", sa.String(255)),
        sa.Column("management_ip", sa.String(64)),
        sa.Column("director_id", sa.Integer(), sa.ForeignKey("directors.id")),
        sa.Column("status", sa.String(32), server_default="unknown", nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_cpes_cpe_id", "cpes", ["cpe_id"])
    op.create_index("ix_cpes_serial_number", "cpes", ["serial_number"])
    op.create_index("ix_cpes_site", "cpes", ["site"])

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subject", sa.String(255), nullable=False, unique=True),
        sa.Column("username", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255)),
        sa.Column("first_name", sa.String(255)),
        sa.Column("last_name", sa.String(255)),
        sa.Column("roles_json", sa.String(2048), server_default="[]", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_users_subject", "users", ["subject"])

    op.create_table(
        "credentials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cpe_id", sa.Integer(), sa.ForeignKey("cpes.id"), nullable=False),
        sa.Column("username", sa.String(255), nullable=False),
        sa.Column("secret_reference", sa.String(255), nullable=False, unique=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(32), server_default="ACTIVE", nullable=False),
        sa.Column("rotation_state", sa.String(32), server_default="ACTIVE", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("retired_at", sa.DateTime(timezone=True)),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True)),
        sa.Column("last_rotated_at", sa.DateTime(timezone=True)),
        sa.Column("next_rotation_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_credentials_cpe_id", "credentials", ["cpe_id"])

    op.create_table(
        "cpe_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_subject", sa.String(255), nullable=False),
        sa.Column("cpe_id", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_cpe_assignments_user_subject", "cpe_assignments", ["user_subject"])
    op.create_index("ix_cpe_assignments_cpe_id", "cpe_assignments", ["cpe_id"])

    op.create_table(
        "access_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("cpe_id", sa.Integer(), sa.ForeignKey("cpes.id"), nullable=False),
        sa.Column("reason", sa.String(1024), nullable=False),
        sa.Column("ticket_reference", sa.String(255)),
        sa.Column("status", sa.String(32), server_default="granted", nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("granted_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("user_subject", sa.String(255)),
        sa.Column("user_username", sa.String(255)),
        sa.Column("user_role", sa.String(255)),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("cpe_id", sa.String(128)),
        sa.Column("ticket_reference", sa.String(255)),
        sa.Column("reason", sa.String(1024)),
        sa.Column("source_ip", sa.String(64)),
        sa.Column("user_agent", sa.String(512)),
        sa.Column("success", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("metadata_json", sa.String(4096)),
    )
    op.create_index("ix_audit_events_timestamp", "audit_events", ["timestamp"])
    op.create_index("ix_audit_events_user_action", "audit_events", ["user_subject", "action"])
    op.create_index("ix_audit_events_cpe_id", "audit_events", ["cpe_id"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("access_requests")
    op.drop_table("cpe_assignments")
    op.drop_table("credentials")
    op.drop_table("users")
    op.drop_table("cpes")
    op.drop_table("directors")