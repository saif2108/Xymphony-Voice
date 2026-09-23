"""Rename RAG document title column to name."""

from collections.abc import Sequence

from alembic import op


revision: str = "0007_rag_document_name"
down_revision: str | Sequence[str] | None = "0006_rag_embedding_dimension"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "documents",
        "title",
        new_column_name="name",
    )


def downgrade() -> None:
    op.alter_column(
        "documents",
        "name",
        new_column_name="title",
    )