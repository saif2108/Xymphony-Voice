"""Provider-neutral context-window history selection."""

from __future__ import annotations

from collections.abc import Sequence

from xymphony_contracts.llm import LLMMessage
from xymphony_runtime.errors import ContextBudgetExceededError
from xymphony_runtime.token_estimate import TokenEstimator, approximate_token_count

SUMMARY_SECTION_HEADER = "[Conversation summary]"


def build_system_with_summary(system_instructions: str, summary_text: str | None) -> str:
    """Combine agent instructions with optional summary context section."""
    if not summary_text:
        return system_instructions
    summary_block = f"{SUMMARY_SECTION_HEADER}\n{summary_text.strip()}"
    if system_instructions.strip():
        return f"{system_instructions.rstrip()}\n\n{summary_block}"
    return summary_block


class ContextBudgetPolicy:
    """Select a suffix of conversation history that fits an input budget.

    Priority (highest first):
    1. system instructions (including optional summary section)
    2. current user message
    3. newest complete historical messages

    Does not mutate inputs, reorder messages, or truncate message content.
    """

    def __init__(self, estimate: TokenEstimator = approximate_token_count) -> None:
        self._estimate = estimate

    def select_history(
        self,
        history: Sequence[LLMMessage],
        *,
        current_user_text: str,
        system_instructions: str,
        max_input_tokens: int,
        summary_text: str | None = None,
    ) -> tuple[LLMMessage, ...]:
        if max_input_tokens < 1:
            raise ContextBudgetExceededError(
                "max_input_tokens must be a positive integer when budgeting is enabled"
            )

        system_prompt = build_system_with_summary(system_instructions, summary_text)
        system_tokens = self._estimate(system_prompt)
        if system_tokens > max_input_tokens:
            raise ContextBudgetExceededError(
                "system instructions exceed the configured context budget"
                if not summary_text
                else "system instructions and conversation summary exceed the context budget"
            )

        remaining = max_input_tokens - system_tokens
        user_tokens = self._estimate(current_user_text)
        if user_tokens > remaining:
            raise ContextBudgetExceededError(
                "current user message exceeds the available context budget"
            )
        remaining -= user_tokens

        selected_newest_first: list[LLMMessage] = []
        for message in reversed(history):
            cost = self._estimate(message.content)
            if cost > remaining:
                break
            selected_newest_first.append(message)
            remaining -= cost

        return tuple(reversed(selected_newest_first))

    def would_drop_history(
        self,
        history: Sequence[LLMMessage],
        *,
        current_user_text: str,
        system_instructions: str,
        max_input_tokens: int,
    ) -> bool:
        """Return True when budgeting without a summary would drop history."""
        selected = self.select_history(
            history,
            current_user_text=current_user_text,
            system_instructions=system_instructions,
            max_input_tokens=max_input_tokens,
            summary_text=None,
        )
        return len(selected) < len(history)
