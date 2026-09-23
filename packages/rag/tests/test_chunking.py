from xymphony_rag.chunking import chunk_text


def test_empty_text_returns_no_chunks() -> None:
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_short_text_returns_one_chunk() -> None:
    text = "This is a short document."

    assert chunk_text(text) == [text]


def test_long_text_creates_multiple_chunks() -> None:
    text = "This is a sentence. " * 100

    chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)

    assert len(chunks) > 1
    assert all(chunk for chunk in chunks)


def test_chunks_have_overlap() -> None:
    text = " ".join(f"word{i}" for i in range(100))

    chunks = chunk_text(
        text,
        chunk_size=100,
        chunk_overlap=20,
    )

    assert len(chunks) > 1

    first_words = set(chunks[0].split())
    second_words = set(chunks[1].split())

    assert first_words.intersection(second_words)


def test_invalid_chunk_size_raises() -> None:
    try:
        chunk_text("hello", chunk_size=0)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")


def test_overlap_must_be_smaller_than_chunk_size() -> None:
    try:
        chunk_text("hello", chunk_size=100, chunk_overlap=100)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")
