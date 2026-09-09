"""Phase 3 Step 8 integration coverage for the context/memory foundation."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from tests.helpers import AGENT_ID, ORG, PROJECT, llm_binding, make_agent_version

from xymphony_contracts import CreateSessionRequest, MessageRole
from xymphony_contracts.llm import LLMRequest, LLMStreamChunk
from xymphony_contracts.provider import CancellationToken, ProviderError, ProviderErrorCode
from xymphony_providers.fake_stt import FakeSTTProvider
from xymphony_providers.fake_tts import FakeTTSProvider
from xymphony_realtime import FakeMediaTransport
from xymphony_runtime import (
    InMemoryConversationRepository,
    InMemoryConversationSummaryRepository,
    InMemorySessionRepository,
    RuntimeInput,
)
from xymphony_runtime.context_budget import SUMMARY_SECTION_HEADER
from xymphony_runtime.conversation import build_text_message, message_text
from xymphony_runtime_worker.bootstrap import VoiceWorkerComponents, build_voice_worker


class RecordingPhase3LLM:
    """Deterministic provider that distinguishes summary and assistant calls."""

    provider_key = "fake"

    def __init__(self, *, summary_delay_seconds: float = 0.0, failed_summaries: int = 0) -> None:
        self.requests: list[LLMRequest] = []
        self.summary_started = asyncio.Event()
        self.summary_delay_seconds = summary_delay_seconds
        self.failed_summaries = failed_summaries
        self._reply_number = 0

    async def stream(
        self,
        request: LLMRequest,
        *,
        cancel: CancellationToken,
    ) -> AsyncIterator[LLMStreamChunk]:
        self.requests.append(request)
        is_summary = "summarize" in request.system.lower()
        if is_summary:
            self.summary_started.set()
            if self.summary_delay_seconds:
                await asyncio.sleep(self.summary_delay_seconds)
            if cancel.cancelled:
                return
            if self.failed_summaries:
                self.failed_summaries -= 1
                raise ProviderError(
                    code=ProviderErrorCode.PROVIDER,
                    message="summary provider unavailable",
                    provider_key=self.provider_key,
                    retryable=True,
                )
            yield LLMStreamChunk(delta="S", finish_reason="stop")
            return

        self._reply_number += 1
        yield LLMStreamChunk(delta=f"answer{self._reply_number:03d}", finish_reason="stop")


def _build_components(
    *,
    version_params: dict[str, object],
    personality: str = "",
    instructions: str = "sys",
    llm: RecordingPhase3LLM | None = None,
) -> tuple[
    VoiceWorkerComponents,
    InMemoryConversationRepository,
    InMemoryConversationSummaryRepository,
    RecordingPhase3LLM,
]:
    version = make_agent_version(
        id=uuid4(),
        personality=personality,
        instructions=instructions,
        llm=llm_binding(params=version_params),
    )
    assert version.config_hash is not None
    sessions = InMemorySessionRepository()
    session = sessions.create_session(
        CreateSessionRequest(
            session_id=uuid4(),
            organization_id=ORG,
            project_id=PROJECT,
            agent_id=AGENT_ID,
            agent_version_id=version.id,
            config_hash=version.config_hash,
        )
    )
    conversation = InMemoryConversationRepository()
    summaries = InMemoryConversationSummaryRepository()
    provider = llm or RecordingPhase3LLM()
    components = build_voice_worker(
        session=session,
        agent_version=version,
        session_repository=sessions,
        conversation_repository=conversation,
        summary_repository=summaries,
        transport=FakeMediaTransport(),
        llm_provider=provider,
        stt_provider=FakeSTTProvider(),
        tts_provider=FakeTTSProvider(chunks=["audio"]),
    )
    return components, conversation, summaries, provider


def _seed_history(
    components: VoiceWorkerComponents,
    conversation: InMemoryConversationRepository,
    *,
    turn_count: int = 3,
) -> None:
    for number in range(1, turn_count + 1):
        for role, text in (
            (MessageRole.USER, f"user{number:04d}"),
            (MessageRole.ASSISTANT, f"answer{number:03d}"),
        ):
            conversation.append_message(
                build_text_message(
                    session_id=components.session.id,
                    turn_id=uuid4(),
                    organization_id=ORG,
                    role=role,
                    text=text,
                )
            )


def _assistant_requests(provider: RecordingPhase3LLM) -> list[LLMRequest]:
    return [request for request in provider.requests if "summarize" not in request.system.lower()]


@pytest.mark.asyncio
async def test_agent_version_configuration_reaches_budgeted_llm_request() -> None:
    components, conversation, _summaries, provider = _build_components(
        personality="Warm.",
        instructions="Be concise.",
        version_params={
            "temperature": 0.4,
            "top_p": 0.85,
            "max_output_tokens": 128,
            "max_input_tokens": 12,
        },
    )
    _seed_history(components, conversation, turn_count=1)

    await components.runtime.start()
    await components.runtime.handle_input(RuntimeInput.text_input("current"))
    await components.runtime.stop()

    request = _assistant_requests(provider)[0]
    assert request.provider_key == "openai"
    assert request.model == "gpt-4o-mini"
    assert request.system == "Warm.\n\nBe concise."
    assert request.temperature == 0.4
    assert request.top_p == 0.85
    assert request.max_output_tokens == 128
    assert request.messages[-1].content == "current"
    # The configured input budget exactly fits the complete prior exchange.
    assert [message.content for message in request.messages] == ["user0001", "answer001", "current"]


@pytest.mark.asyncio
async def test_long_conversation_uses_summary_newest_history_and_continues() -> None:
    components, conversation, summaries, provider = _build_components(
        version_params={
            "temperature": 0.2,
            "top_p": 0.9,
            "max_output_tokens": 64,
            "max_input_tokens": 16,
        }
    )

    await components.runtime.start()
    for number in range(1, 6):
        await components.runtime.handle_input(RuntimeInput.text_input(f"user{number:04d}"))
    await components.runtime.stop()

    stored_summary = summaries.get_latest(components.session.id, organization_id=ORG)
    assert stored_summary is not None
    assert stored_summary.through_sequence >= 1
    assert len(conversation.list_messages(components.session.id, organization_id=ORG)) == 10

    requests = _assistant_requests(provider)
    assert len(requests) == 5
    summarized_request = next(
        request for request in requests if SUMMARY_SECTION_HEADER in request.system
    )
    assert summarized_request.system.count(SUMMARY_SECTION_HEADER) == 1
    assert summarized_request.messages[-1].content in {"user0004", "user0005"}
    assert "answer003" in [message.content for message in summarized_request.messages]
    assert "user0001" not in [message.content for message in summarized_request.messages]
    assert all(message.role != MessageRole.SYSTEM for message in summarized_request.messages)
    assert all(request.temperature == 0.2 for request in requests)
    assert all(request.top_p == 0.9 for request in requests)
    assert all(request.max_output_tokens == 64 for request in requests)


@pytest.mark.asyncio
async def test_cancelled_summary_cannot_contaminate_a_later_turn() -> None:
    provider = RecordingPhase3LLM(summary_delay_seconds=0.05)
    components, conversation, summaries, provider = _build_components(
        version_params={"max_input_tokens": 16},
        llm=provider,
    )
    _seed_history(components, conversation)

    await components.runtime.start()
    cancelled = asyncio.create_task(
        components.runtime.handle_input(RuntimeInput.text_input("cancel-me"))
    )
    await asyncio.wait_for(provider.summary_started.wait(), timeout=1)
    turn_id = components.runtime.current_turn_id
    assert turn_id is not None
    await components.runtime.handle_input(RuntimeInput.cancel_turn(turn_id))
    await cancelled

    assert summaries.get_latest(components.session.id) is None
    assert len(_assistant_requests(provider)) == 0
    assert len(conversation.list_messages(components.session.id)) == 6

    provider.summary_delay_seconds = 0
    await components.runtime.handle_input(RuntimeInput.text_input("after-cancel"))
    await components.runtime.stop()

    messages = conversation.list_messages(components.session.id, organization_id=ORG)
    assert [message_text(message) for message in messages[-2:]] == ["after-cancel", "answer001"]
    assert summaries.get_latest(components.session.id) is not None


@pytest.mark.asyncio
async def test_summary_failure_is_soft_and_a_later_turn_retries_successfully() -> None:
    provider = RecordingPhase3LLM(failed_summaries=1)
    components, conversation, summaries, provider = _build_components(
        version_params={"max_input_tokens": 16},
        llm=provider,
    )
    _seed_history(components, conversation)

    await components.runtime.start()
    await components.runtime.handle_input(RuntimeInput.text_input("first-after-failure"))
    assert summaries.get_latest(components.session.id) is None
    assert len(_assistant_requests(provider)) == 1

    await components.runtime.handle_input(RuntimeInput.text_input("retry-summary"))
    await components.runtime.stop()

    summary = summaries.get_latest(components.session.id, organization_id=ORG)
    assert summary is not None
    assert summary.through_sequence >= 1
    messages = conversation.list_messages(components.session.id, organization_id=ORG)
    assert [message_text(message) for message in messages[-4:]] == [
        "first-after-failure",
        "answer001",
        "retry-summary",
        "answer002",
    ]


@pytest.mark.asyncio
async def test_active_worker_uses_the_session_pinned_version_not_a_newer_snapshot() -> None:
    components, _conversation, _summaries, provider = _build_components(
        personality="Pinned personality.",
        instructions="Pinned instructions.",
        version_params={},
    )
    newer_version = make_agent_version(
        id=uuid4(),
        version_n=2,
        personality="New personality.",
        instructions="New instructions.",
        llm=llm_binding(model="newer-model"),
    )
    assert newer_version.id != components.session.agent_version_id

    await components.runtime.start()
    await components.runtime.handle_input(RuntimeInput.text_input("hello"))
    await components.runtime.stop()

    request = _assistant_requests(provider)[0]
    assert components.runtime.context.agent_version_id == components.session.agent_version_id
    assert request.system == "Pinned personality.\n\nPinned instructions."
    assert request.model == "gpt-4o-mini"
