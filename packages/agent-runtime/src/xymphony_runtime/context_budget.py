"""Provider-neutral context-window history selection."""

from __future__ import annotations

from collections.abc import Sequence

from xymphony_contracts.llm import LLMMessage
from xymphony_runtime.errors import ContextBudgetExceededError
from xymphony_runtime.token_estimate import TokenEstimator, approximate_token_count


class ContextBudgetPolicy:
    """Select a suffix of conversation history that fits an input budget.

    Priority: system instructions and the current user message are always
    reserved first. Remaining budget is filled with the newest complete
    history messages that fit (oldest dropped first). Does not mutate inputs,
    reorder messages, truncate message content, or access repositories.
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
    ) -> tuple[LLMMessage, ...]:
        if max_input_tokens < 1:
            raise ContextBudgetExceededError(
                "max_input_tokens must be a positive integer when budgeting is enabled"
            )

        system_tokens = self._estimate(system_instructions)
        if system_tokens > max_input_tokens:
            raise ContextBudgetExceededError(
                "system instructions exceed the configured context budget"
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
