"""Provider-neutral LLM request assembly from conversation history."""

from __future__ import annotations

from collections.abc import Sequence

from xymphony_contracts.llm import LLMMessage, LLMRequest, LLMRole
from xymphony_contracts.session import Message
from xymphony_runtime.conversation import committed_messages_to_llm
from xymphony_runtime.llm_config import LLMRuntimeConfig


class LLMContextAssembler:
    """Pure assembler: conversation history + current utterance → LLMRequest.

    Does not access repositories, providers, or persistence. Does not truncate
    or count tokens. Does not mutate the supplied history sequence.
    """

    def assemble(
        self,
        *,
        history: Sequence[Message],
        current_user_text: str,
        config: LLMRuntimeConfig,
    ) -> LLMRequest:
        llm_history = committed_messages_to_llm(tuple(history))
        return LLMRequest(
            provider_key=config.provider_key,
            model=config.model,
            messages=(
                *llm_history,
                LLMMessage(role=LLMRole.USER, content=current_user_text),
            ),
            system=config.system_instructions,
            params=config.params,
        )
