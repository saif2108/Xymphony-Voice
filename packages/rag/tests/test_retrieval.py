from xymphony_rag.retrieval import RetrievalResult


def test_retrieval_result_stores_metadata() -> None:
    result = RetrievalResult(
        content="Xymphony Voice is a realtime AI platform.",
        score=0.92,
        document_id="document-1",
        chunk_id="chunk-1",
    )

    assert result.content == "Xymphony Voice is a realtime AI platform."
    assert result.score == 0.92
    assert result.document_id == "document-1"
    assert result.chunk_id == "chunk-1"