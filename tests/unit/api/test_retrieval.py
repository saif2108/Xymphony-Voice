from uuid import UUID

from xymphony_api.retrieval import DatabaseRetriever


class FakeEmbeddingProvider:
    def embed(self, text: str) -> list[float]:
        assert text == "How does this work?"
        return [0.1, 0.2]


class FakeRepository:
    def search_hybrid_scored(self, **kwargs: object) -> list[tuple[object, float]]:
        assert kwargs["query"] == "How does this work?"
        assert kwargs["query_embedding"] == [0.1, 0.2]
        assert kwargs["limit"] == 3

        row = type(
            "DocumentChunk",
            (),
            {
                "content": "It works through retrieval.",
                "document_id": UUID("00000000-0000-0000-0000-000000000001"),
                "id": UUID("00000000-0000-0000-0000-000000000002"),
            },
        )()
        return [(row, 0.87)]


def test_database_retriever_maps_scored_rows() -> None:
    retriever = DatabaseRetriever(
        repository=FakeRepository(),  # type: ignore[arg-type]
        embedding_provider=FakeEmbeddingProvider(),  # type: ignore[arg-type]
        agent_version_id=UUID("00000000-0000-0000-0000-000000000003"),
    )

    results = retriever.retrieve(query="How does this work?", limit=3)

    assert results[0].content == "It works through retrieval."
    assert results[0].score == 0.87
    assert results[0].document_id == "00000000-0000-0000-0000-000000000001"
    assert results[0].chunk_id == "00000000-0000-0000-0000-000000000002"
