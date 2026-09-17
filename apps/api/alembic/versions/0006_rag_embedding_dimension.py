"""Change RAG embedding dimension to 384."""

from collections.abc import Sequence

from alembic import op


revision: str = "0006_rag_embedding_dimension"
down_revision: str | Sequence[str] | None = "0005_p4_knowledge_rag"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE document_chunks
        ALTER COLUMN embedding TYPE vector(384)
        USING NULL
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE document_chunks
        ALTER COLUMN embedding TYPE vector(1536)
        USING NULL
        """
    )