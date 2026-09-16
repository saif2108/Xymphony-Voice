"""Phase 4: tool_definitions and agent_version_tools (control-plane tool management)."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_p4_tool_management"
down_revision: str | Sequence[str] | None = "0003_p3_conversation_summaries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tool_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("tool_type", sa.String(length=32), nullable=False, server_default="function"),
        sa.Column(
            "parameters",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{\"type\": \"object\", \"properties\": {}}'::jsonb"),
        ),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "name", name="uq_tool_defs_project_name"),
    )
    op.create_index(
        "ix_tool_definitions_organization_id", "tool_definitions", ["organization_id"]
    )
    op.create_index("ix_tool_definitions_project_id", "tool_definitions", ["project_id"])

    op.create_table(
        "agent_version_tools",
        sa.Column("agent_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tool_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["agent_version_id"], ["agent_versions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tool_definition_id"], ["tool_definitions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("agent_version_id", "tool_definition_id"),
    )


def downgrade() -> None:
    op.drop_table("agent_version_tools")
    op.drop_index("ix_tool_definitions_project_id", table_name="tool_definitions")
    op.drop_index("ix_tool_definitions_organization_id", table_name="tool_definitions")
    op.drop_table("tool_definitions")