"""Approximate, provider-neutral token estimation for context budgeting.

This is an *estimate*, not an exact provider/model tokenizer count.
It exists so budgeting can be deterministic without vendor SDKs.
A future exact tokenizer can replace this behind TokenEstimator.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol


class TokenEstimator(Protocol):
    """Callable estimate of token count for a text string."""

    def __call__(self, text: str) -> int: ...


def approximate_token_count(text: str) -> int:
    """Rough token estimate: ~4 characters per token (ceiling).

    Empty text counts as 0. Non-empty text always counts at least 1.
    Not accurate for any specific provider tokenizer.
    """
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


TokenEstimatorFn = Callable[[str], int]
