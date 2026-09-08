"""Phase 3 Step 3: conversation_summaries (rolling derived context)."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_p3_conversation_summaries"
down_revision: str | Sequence[str] | None = "0002_p2_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversation_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("through_sequence", sa.Integer(), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("source_message_count", sa.Integer(), nullable=False, server_default="0"),
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
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", name="uq_conversation_summaries_session_id"),
    )
    op.create_index(
        "ix_conversation_summaries_session_id",
        "conversation_summaries",
        ["session_id"],
        unique=True,
    )
    op.create_index(
        "ix_conversation_summaries_organization_id",
        "conversation_summaries",
        ["organization_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_conversation_summaries_organization_id", table_name="conversation_summaries")
    op.drop_index("ix_conversation_summaries_session_id", table_name="conversation_summaries")
    op.drop_table("conversation_summaries")
