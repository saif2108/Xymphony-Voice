"""Provider-neutral LLM request assembly from conversation history."""

from __future__ import annotations

from collections.abc import Sequence

from xymphony_contracts.llm import LLMMessage, LLMRequest, LLMRole, LLMToolDefinition
from xymphony_contracts.session import Message
from xymphony_runtime.context_budget import (
    ContextBudgetPolicy,
    build_system_prompt,
)
from xymphony_runtime.conversation import committed_messages_to_llm
from xymphony_runtime.errors import ContextBudgetExceededError
from xymphony_runtime.llm_config import LLMRuntimeConfig


class LLMContextAssembler:
    """Pure assembler: conversation history + current utterance → LLMRequest.

    Does not access repositories, providers, or persistence. Does not mutate
    the supplied history sequence. When ``config.max_input_tokens`` is set,
    applies :class:`ContextBudgetPolicy` before building the request.
    Optional ``summary_text`` and ``knowledge_text`` are appended to
    ``LLMRequest.system`` as dedicated context sections (not conversation turns).
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
        knowledge_text: str | None = None,
        memory_text: str | None = None,
        tools: Sequence[LLMToolDefinition] = (),
        extra_messages: Sequence[LLMMessage] = (),
    ) -> LLMRequest:
        llm_history = committed_messages_to_llm(tuple(history))
        effective_summary = summary_text
        effective_knowledge = knowledge_text
        effective_memory = memory_text
        if config.max_input_tokens is not None:
            try:
                llm_history = self._budget_policy.select_history(
                    llm_history,
                    current_user_text=current_user_text,
                    system_instructions=config.system_instructions,
                    max_input_tokens=config.max_input_tokens,
                    summary_text=effective_summary,
                    knowledge_text=effective_knowledge,
                    memory_text=effective_memory,
                )
            except ContextBudgetExceededError:
                # Soft-fail: drop memory first, then knowledge, then summary
                if effective_memory is not None:
                    effective_memory = None
                    try:
                        llm_history = self._budget_policy.select_history(
                            committed_messages_to_llm(tuple(history)),
                            current_user_text=current_user_text,
                            system_instructions=config.system_instructions,
                            max_input_tokens=config.max_input_tokens,
                            summary_text=effective_summary,
                            knowledge_text=effective_knowledge,
                            memory_text=None,
                        )
                    except ContextBudgetExceededError:
                        if effective_knowledge is not None:
                            effective_knowledge = None
                            try:
                                llm_history = self._budget_policy.select_history(
                                    committed_messages_to_llm(tuple(history)),
                                    current_user_text=current_user_text,
                                    system_instructions=config.system_instructions,
                                    max_input_tokens=config.max_input_tokens,
                                    summary_text=effective_summary,
                                    knowledge_text=None,
                                    memory_text=None,
                                )
                            except ContextBudgetExceededError:
                                if effective_summary is not None:
                                    effective_summary = None
                                    llm_history = self._budget_policy.select_history(
                                        committed_messages_to_llm(tuple(history)),
                                        current_user_text=current_user_text,
                                        system_instructions=config.system_instructions,
                                        max_input_tokens=config.max_input_tokens,
                                        summary_text=None,
                                        knowledge_text=None,
                                        memory_text=None,
                                    )
                                else:
                                    raise
                        elif effective_summary is not None:
                            effective_summary = None
                            llm_history = self._budget_policy.select_history(
                                committed_messages_to_llm(tuple(history)),
                                current_user_text=current_user_text,
                                system_instructions=config.system_instructions,
                                max_input_tokens=config.max_input_tokens,
                                summary_text=None,
                                knowledge_text=None,
                                memory_text=None,
                            )
                        else:
                            raise
                elif effective_knowledge is not None:
                    effective_knowledge = None
                    try:
                        llm_history = self._budget_policy.select_history(
                            committed_messages_to_llm(tuple(history)),
                            current_user_text=current_user_text,
                            system_instructions=config.system_instructions,
                            max_input_tokens=config.max_input_tokens,
                            summary_text=effective_summary,
                            knowledge_text=None,
                            memory_text=None,
                        )
                    except ContextBudgetExceededError:
                        if effective_summary is not None:
                            effective_summary = None
                            llm_history = self._budget_policy.select_history(
                                committed_messages_to_llm(tuple(history)),
                                current_user_text=current_user_text,
                                system_instructions=config.system_instructions,
                                max_input_tokens=config.max_input_tokens,
                                summary_text=None,
                                knowledge_text=None,
                                memory_text=None,
                            )
                        else:
                            raise
                elif effective_summary is not None:
                    effective_summary = None
                    llm_history = self._budget_policy.select_history(
                        committed_messages_to_llm(tuple(history)),
                        current_user_text=current_user_text,
                        system_instructions=config.system_instructions,
                        max_input_tokens=config.max_input_tokens,
                        summary_text=None,
                        knowledge_text=None,
                        memory_text=None,
                    )
                else:
                    raise

        return LLMRequest(
            provider_key=config.provider_key,
            model=config.model,
            messages=(
                *llm_history,
                LLMMessage(role=LLMRole.USER, content=current_user_text),
                *extra_messages,
            ),
            tools=tuple(tools),
            system=build_system_prompt(
                config.system_instructions,
                summary_text=effective_summary,
                knowledge_text=effective_knowledge,
                memory_text=effective_memory,
            ),
            params=config.params,
            temperature=config.temperature,
            max_output_tokens=config.max_output_tokens,
            top_p=config.top_p,
        )
