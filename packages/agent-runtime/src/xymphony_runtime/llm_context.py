"""Provider-neutral LLM request assembly from conversation history."""

from __future__ import annotations

from collections.abc import Sequence

from xymphony_contracts.llm import LLMMessage, LLMRequest, LLMRole
from xymphony_contracts.session import Message
from xymphony_runtime.context_budget import ContextBudgetPolicy, build_system_with_summary
from xymphony_runtime.conversation import committed_messages_to_llm
from xymphony_runtime.errors import ContextBudgetExceededError
from xymphony_runtime.llm_config import LLMRuntimeConfig


class LLMContextAssembler:
    """Pure assembler: conversation history + current utterance → LLMRequest.

    Does not access repositories, providers, or persistence. Does not mutate
    the supplied history sequence. When ``config.max_input_tokens`` is set,
    applies :class:`ContextBudgetPolicy` before building the request.
    Optional ``summary_text`` is appended to ``LLMRequest.system`` as a
    dedicated context section (not a conversation turn).
    """

    def __init__(self, budget_policy: ContextBudgetPolicy | None = None) -> None:
        self._budget_policy = budget_policy or ContextBudgetPolicy()

    def assemble(
        self,
        *,
        history: Sequence[Message],
        current_user_text: str,
        config: LLMRuntimeConfig,
        summary_text: str | None = None,
    ) -> LLMRequest:
        llm_history = committed_messages_to_llm(tuple(history))
        effective_summary = summary_text
        if config.max_input_tokens is not None:
            try:
                llm_history = self._budget_policy.select_history(
                    llm_history,
                    current_user_text=current_user_text,
                    system_instructions=config.system_instructions,
                    max_input_tokens=config.max_input_tokens,
                    summary_text=effective_summary,
                )
            except ContextBudgetExceededError:
                if effective_summary is None:
                    raise
                # Soft-fail oversized summary: continue with Step 2 budgeted history.
                effective_summary = None
                llm_history = self._budget_policy.select_history(
                    committed_messages_to_llm(tuple(history)),
                    current_user_text=current_user_text,
                    system_instructions=config.system_instructions,
                    max_input_tokens=config.max_input_tokens,
                    summary_text=None,
                )

        return LLMRequest(
            provider_key=config.provider_key,
            model=config.model,
            messages=(
                *llm_history,
                LLMMessage(role=LLMRole.USER, content=current_user_text),
            ),
            system=build_system_with_summary(config.system_instructions, effective_summary),
            params=config.params,
            temperature=config.temperature,
            max_output_tokens=config.max_output_tokens,
            top_p=config.top_p,
        )
