from __future__ import annotations

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150


def chunk_text(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Split text into overlapping chunks while preserving natural boundaries."""
    if not text.strip():
        return []

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")

    if chunk_overlap < 0:
        raise ValueError("chunk_overlap cannot be negative")

    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    normalized_text = " ".join(text.split())

    if len(normalized_text) <= chunk_size:
        return [normalized_text]

    separators = ["\n\n", "\n", ". ", "? ", "! ", " "]

    chunks: list[str] = []
    remaining = normalized_text

    while len(remaining) > chunk_size:
        split_at = _find_split_position(
            remaining,
            chunk_size,
            separators,
        )

        chunk = remaining[:split_at].strip()

        if chunk:
            chunks.append(chunk)

        overlap_start = max(0, split_at - chunk_overlap)
        remaining = remaining[overlap_start:].strip()

        if len(remaining) >= len(normalized_text):
            break

    if remaining:
        chunks.append(remaining)

    return chunks


def _find_split_position(
    text: str,
    chunk_size: int,
    separators: list[str],
) -> int:
    """Find the best natural boundary before the maximum chunk size."""
    boundary = min(chunk_size, len(text))

    for separator in separators:
        position = text.rfind(separator, 0, boundary)

        if position > 0:
            return position + len(separator)

    return boundary
