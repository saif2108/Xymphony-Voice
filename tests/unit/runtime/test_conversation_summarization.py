"""Phase 3 Step 3 — conversation summarization tests."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from tests.helpers import ORG, SESSION_ID, VERSION_ID, make_session

from xymphony_contracts.content import ContentPart
from xymphony_contracts.enums import ContentPartType, EventType, MessageRole, MessageStatus
from xymphony_contracts.llm import LLMRequest, LLMRole, ProviderError, ProviderErrorCode
from xymphony_contracts.provider import CancellationToken
from xymphony_contracts.session import Message
from xymphony_contracts.summary import ConversationSummary
from xymphony_providers.fake_tts import FakeTTSProvider
from xymphony_runtime import (
    AgentRuntime,
    ConversationSummarizer,
    InMemoryConversationRepository,
    InMemoryConversationSummaryRepository,
    InMemorySessionRepository,
    LLMContextAssembler,
    LLMRuntimeConfig,
    RuntimeInput,
)
from xymphony_runtime.cancellation import EventCancellationToken
from xymphony_runtime.context_budget import SUMMARY_SECTION_HEADER, build_system_with_summary
from xymphony_runtime.conversation import build_text_message
from xymphony_runtime.turn import RuntimeTurnLifecycleState


def _text_message(role: MessageRole, text: str, *, sequence: int) -> Message:
    return Message(
        id=uuid4(),
        session_id=SESSION_ID,
        turn_id=uuid4(),
        organization_id=ORG,
        role=role,
        status=MessageStatus.COMMITTED,
        parts=(ContentPart(type=ContentPartType.TEXT, payload={"text": text}),),
        created_at=datetime(2026, 9, 8, 12, 0, 0, tzinfo=UTC),
        metadata={"sequence": sequence},
    )


def _config(**overrides: object) -> LLMRuntimeConfig:
    data: dict[str, object] = {
        "provider_key": "fake",
        "model": "fake-model",
        "system_instructions": "sys",
        "params": {},
        "max_input_tokens": None,
    }
    data.update(overrides)
    return LLMRuntimeConfig(**data)  # type: ignore[arg-type]


# ~4 tokens each so a modest budget drops older turns while still allowing a
# short "[Conversation summary]" section to fit with system + current user.
_BULKY = "abcdefghijklm"


def _bulky_history(*, count: int = 6) -> tuple[Message, ...]:
    return tuple(
        _text_message(
            MessageRole.USER if index % 2 else MessageRole.ASSISTANT,
            f"{_BULKY}{index}",
            sequence=index,
        )
        for index in range(1, count + 1)
    )


# system(1) + user(1) + room for ~2 bulky msgs (~8) → older history drops;
# short summary still fits under the same ceiling.
_TRIGGER_BUDGET = 12


class DualModeFakeLLM:
    """Returns different streams for summary vs conversation requests."""

    provider_key = "fake"

    def __init__(
        self,
        *,
        summary_chunks: list[str] | None = None,
        reply_chunks: list[str] | None = None,
        fail_summary_with: ProviderError | None = None,
        delay_seconds: float = 0,
    ) -> None:
        self.summary_chunks = summary_chunks or ["Prior context saved."]
        self.reply_chunks = reply_chunks or ["assistant reply"]
        self.fail_summary_with = fail_summary_with
        self.delay_seconds = delay_seconds
        self.requests: list[LLMRequest] = []

    async def stream(
        self,
        request: LLMRequest,
        *,
        cancel: CancellationToken,
    ) -> AsyncIterator[object]:
        from xymphony_contracts.llm import LLMStreamChunk

        self.requests.append(request)
        is_summary = "summarize" in request.system.lower()
        if is_summary and self.fail_summary_with is not None:
            raise self.fail_summary_with
        chunks = self.summary_chunks if is_summary else self.reply_chunks
        for index, delta in enumerate(chunks):
            if cancel.cancelled:
                return
            if self.delay_seconds:
                await asyncio.sleep(self.delay_seconds)
            if cancel.cancelled:
                return
            finish_reason = "stop" if index == len(chunks) - 1 else None
            yield LLMStreamChunk(delta=delta, finish_reason=finish_reason)


def test_summary_repository_create_read_upsert() -> None:
    repo = InMemoryConversationSummaryRepository()
    first = ConversationSummary(
        id=uuid4(),
        session_id=SESSION_ID,
        organization_id=ORG,
        agent_version_id=VERSION_ID,
        through_sequence=2,
        summary_text="First summary",
        source_message_count=2,
        created_at=datetime.now(tz=UTC),
    )
    repo.upsert(first)
    loaded = repo.get_latest(SESSION_ID, organization_id=ORG)
    assert loaded is not None
    assert loaded.summary_text == "First summary"
    assert loaded.through_sequence == 2

    updated = first.model_copy(update={"through_sequence": 4, "summary_text": "Rolled"})
    repo.upsert(updated)
    again = repo.get_latest(SESSION_ID)
    assert again is not None
    assert again.through_sequence == 4
    assert again.summary_text == "Rolled"
    assert len(repo.summaries) == 1


def test_summary_repository_tenant_isolation() -> None:
    repo = InMemoryConversationSummaryRepository()
    repo.upsert(
        ConversationSummary(
            id=uuid4(),
            session_id=SESSION_ID,
            organization_id=ORG,
            agent_version_id=VERSION_ID,
            through_sequence=1,
            summary_text="mine",
            source_message_count=1,
            created_at=datetime.now(tz=UTC),
        )
    )
    assert repo.get_latest(SESSION_ID, organization_id=uuid4()) is None
    assert repo.get_latest(uuid4(), organization_id=ORG) is None


def test_build_system_with_summary_section() -> None:
    combined = build_system_with_summary("Be helpful.", "User likes tea.")
    assert combined.startswith("Be helpful.")
    assert SUMMARY_SECTION_HEADER in combined
    assert "User likes tea." in combined
    assert combined.count(SUMMARY_SECTION_HEADER) == 1


def test_assembler_injects_summary_once_in_system() -> None:
    history = (
        _text_message(MessageRole.USER, "U2xx", sequence=3),
        _text_message(MessageRole.ASSISTANT, "A2xx", sequence=4),
    )
    request = LLMContextAssembler().assemble(
        history=history,
        current_user_text="curr",
        config=_config(system_instructions="sys", max_input_tokens=20),
        summary_text="Older chat about cats.",
    )
    assert SUMMARY_SECTION_HEADER in request.system
    assert request.system.count(SUMMARY_SECTION_HEADER) == 1
    assert request.messages[-1].role == LLMRole.USER
    assert request.messages[-1].content == "curr"
    assert all(message.role != LLMRole.SYSTEM for message in request.messages)


def test_no_summarization_when_budget_disabled() -> None:
    async def _run() -> None:
        llm = DualModeFakeLLM()
        summaries = InMemoryConversationSummaryRepository()
        summarizer = ConversationSummarizer(
            llm_provider=llm,
            llm_config=_config(max_input_tokens=None),
            summary_repository=summaries,
        )
        history = (
            _text_message(MessageRole.USER, "U1xx", sequence=1),
            _text_message(MessageRole.ASSISTANT, "A1xx", sequence=2),
        )
        result = await summarizer.prepare(
            session_id=SESSION_ID,
            organization_id=ORG,
            agent_version_id=VERSION_ID,
            history=history,
            current_user_text="hi",
            cancel=EventCancellationToken(),
            is_turn_cancelled=lambda: False,
        )
        assert result.summary_text is None
        assert result.history_for_assembly == history
        assert llm.requests == []
        assert summaries.get_latest(SESSION_ID) is None

    asyncio.run(_run())


def test_no_summarization_when_history_fits() -> None:
    async def _run() -> None:
        llm = DualModeFakeLLM()
        summaries = InMemoryConversationSummaryRepository()
        summarizer = ConversationSummarizer(
            llm_provider=llm,
            llm_config=_config(system_instructions="sys", max_input_tokens=20),
            summary_repository=summaries,
        )
        history = (
            _text_message(MessageRole.USER, "U1xx", sequence=1),
            _text_message(MessageRole.ASSISTANT, "A1xx", sequence=2),
        )
        result = await summarizer.prepare(
            session_id=SESSION_ID,
            organization_id=ORG,
            agent_version_id=VERSION_ID,
            history=history,
            current_user_text="curr",
            cancel=EventCancellationToken(),
            is_turn_cancelled=lambda: False,
        )
        assert result.summary_text is None
        assert summaries.get_latest(SESSION_ID) is None
        assert llm.requests == []

    asyncio.run(_run())


@pytest.mark.asyncio
async def test_summarization_triggers_and_advances_through_sequence() -> None:
    llm = DualModeFakeLLM(summary_chunks=["ok"])
    summaries = InMemoryConversationSummaryRepository()
    conversation = InMemoryConversationRepository()
    history: list[Message] = []
    for index in range(1, 7):
        role = MessageRole.USER if index % 2 else MessageRole.ASSISTANT
        history.append(
            conversation.append_message(
                build_text_message(
                    session_id=SESSION_ID,
                    turn_id=uuid4(),
                    organization_id=ORG,
                    role=role,
                    text=f"{_BULKY}{index}",
                )
            )
        )

    summarizer = ConversationSummarizer(
        llm_provider=llm,
        llm_config=_config(system_instructions="sys", max_input_tokens=_TRIGGER_BUDGET),
        summary_repository=summaries,
    )
    result = await summarizer.prepare(
        session_id=SESSION_ID,
        organization_id=ORG,
        agent_version_id=VERSION_ID,
        history=tuple(history),
        current_user_text="curr",
        cancel=EventCancellationToken(),
        is_turn_cancelled=lambda: False,
    )
    assert result.summary_text == "ok"
    stored = summaries.get_latest(SESSION_ID)
    assert stored is not None
    assert stored.through_sequence >= 1
    assert conversation.list_messages(SESSION_ID) == tuple(history)
    assert any("summarize" in request.system.lower() for request in llm.requests)
    assert all(message.role in (MessageRole.USER, MessageRole.ASSISTANT) for message in history)
    assert len(result.history_for_assembly) < len(history)

    llm.requests.clear()
    second = await summarizer.prepare(
        session_id=SESSION_ID,
        organization_id=ORG,
        agent_version_id=VERSION_ID,
        history=tuple(history),
        current_user_text="curr",
        cancel=EventCancellationToken(),
        is_turn_cancelled=lambda: False,
    )
    assert second.summary_text == "ok"
    assert not any("summarize" in request.system.lower() for request in llm.requests)
    assert summaries.get_latest(SESSION_ID) is not None
    assert summaries.get_latest(SESSION_ID).through_sequence == stored.through_sequence


@pytest.mark.asyncio
async def test_summary_failure_soft_falls_back() -> None:
    llm = DualModeFakeLLM(
        fail_summary_with=ProviderError(
            code=ProviderErrorCode.PROVIDER,
            message="summary down",
            provider_key="fake",
            retryable=True,
        )
    )
    summaries = InMemoryConversationSummaryRepository()
    history = _bulky_history()
    summarizer = ConversationSummarizer(
        llm_provider=llm,
        llm_config=_config(system_instructions="sys", max_input_tokens=_TRIGGER_BUDGET),
        summary_repository=summaries,
    )
    result = await summarizer.prepare(
        session_id=SESSION_ID,
        organization_id=ORG,
        agent_version_id=VERSION_ID,
        history=history,
        current_user_text="curr",
        cancel=EventCancellationToken(),
        is_turn_cancelled=lambda: False,
    )
    assert result.summary_text is None
    assert result.history_for_assembly == history
    assert summaries.get_latest(SESSION_ID) is None


@pytest.mark.asyncio
async def test_cancelled_summarization_does_not_persist() -> None:
    llm = DualModeFakeLLM(summary_chunks=["a", "b", "c"], delay_seconds=0.05)
    summaries = InMemoryConversationSummaryRepository()
    history = _bulky_history()
    summarizer = ConversationSummarizer(
        llm_provider=llm,
        llm_config=_config(system_instructions="sys", max_input_tokens=_TRIGGER_BUDGET),
        summary_repository=summaries,
    )
    cancel = EventCancellationToken()

    async def _prepare() -> object:
        return await summarizer.prepare(
            session_id=SESSION_ID,
            organization_id=ORG,
            agent_version_id=VERSION_ID,
            history=history,
            current_user_text="curr",
            cancel=cancel,
            is_turn_cancelled=lambda: cancel.cancelled,
        )

    task = asyncio.create_task(_prepare())
    await asyncio.sleep(0.02)
    cancel.cancel()
    await task
    assert summaries.get_latest(SESSION_ID) is None


@pytest.mark.asyncio
async def test_runtime_succeeds_after_summary_failure() -> None:
    from xymphony_contracts import CreateSessionRequest
    from xymphony_runtime import RuntimeContext, TTSRuntimeConfig

    llm = DualModeFakeLLM(
        fail_summary_with=ProviderError(
            code=ProviderErrorCode.PROVIDER,
            message="summary down",
            provider_key="fake",
        ),
        reply_chunks=["ok"],
    )
    conversation = InMemoryConversationRepository()
    summaries = InMemoryConversationSummaryRepository()
    sessions = InMemorySessionRepository()
    contract = make_session()
    assert contract.config_hash is not None
    sessions.create_session(
        CreateSessionRequest(
            session_id=contract.id,
            organization_id=contract.organization_id,
            project_id=contract.project_id,
            agent_id=contract.agent_id,
            agent_version_id=contract.agent_version_id,
            config_hash=contract.config_hash,
        )
    )
    for index in range(1, 7):
        role = MessageRole.USER if index % 2 else MessageRole.ASSISTANT
        conversation.append_message(
            build_text_message(
                session_id=contract.id,
                turn_id=uuid4(),
                organization_id=ORG,
                role=role,
                text=f"{_BULKY}{index}",
            )
        )

    runtime = AgentRuntime(
        RuntimeContext(
            session_id=contract.id,
            organization_id=contract.organization_id,
            project_id=contract.project_id,
            agent_id=contract.agent_id,
            agent_version_id=contract.agent_version_id,
            config_hash=contract.config_hash,
        ),
        llm_provider=llm,
        llm_config=_config(system_instructions="sys", max_input_tokens=_TRIGGER_BUDGET),
        tts_provider=FakeTTSProvider(chunks=["audio"]),
        tts_config=TTSRuntimeConfig(provider_key="fake", voice_ref="v"),
        session_repository=sessions,
        conversation_repository=conversation,
        summary_repository=summaries,
    )
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("curr"))
    assert runtime.turns[0].state == RuntimeTurnLifecycleState.COMPLETED
    assert any(event.type == EventType.LLM_RESPONSE for event in runtime.admitted_events)
    assert summaries.get_latest(contract.id) is None
    await runtime.stop()


@pytest.mark.asyncio
async def test_summary_enters_system_once_and_respects_budget() -> None:
    llm = DualModeFakeLLM(summary_chunks=["ok"])
    summaries = InMemoryConversationSummaryRepository()
    history = _bulky_history()
    summarizer = ConversationSummarizer(
        llm_provider=llm,
        llm_config=_config(system_instructions="sys", max_input_tokens=_TRIGGER_BUDGET),
        summary_repository=summaries,
    )
    prepared = await summarizer.prepare(
        session_id=SESSION_ID,
        organization_id=ORG,
        agent_version_id=VERSION_ID,
        history=history,
        current_user_text="curr",
        cancel=EventCancellationToken(),
        is_turn_cancelled=lambda: False,
    )
    assert prepared.summary_text == "ok"
    request = LLMContextAssembler().assemble(
        history=prepared.history_for_assembly,
        current_user_text="curr",
        config=_config(system_instructions="sys", max_input_tokens=_TRIGGER_BUDGET),
        summary_text=prepared.summary_text,
    )
    assert request.system.count(SUMMARY_SECTION_HEADER) == 1
    assert "ok" in request.system
    assert request.messages[-1].role == LLMRole.USER
    assert request.messages[-1].content == "curr"
    assert all(message.role != LLMRole.SYSTEM for message in request.messages)
    from xymphony_runtime.token_estimate import approximate_token_count

    total = approximate_token_count(request.system) + sum(
        approximate_token_count(message.content) for message in request.messages
    )
    assert total <= _TRIGGER_BUDGET
    # Recent history stays chronological when present
    contents = [message.content for message in request.messages[:-1]]
    assert contents == sorted(contents, key=lambda text: int(text.replace(_BULKY, "") or "0"))


def test_oversized_summary_soft_falls_in_assembler() -> None:
    huge = "s" * 200
    request = LLMContextAssembler().assemble(
        history=(_text_message(MessageRole.USER, "U2xx", sequence=1),),
        current_user_text="curr",
        config=_config(system_instructions="sys", max_input_tokens=5),
        summary_text=huge,
    )
    assert SUMMARY_SECTION_HEADER not in request.system
    assert request.system == "sys"
    assert request.messages[-1].content == "curr"


def test_memory_append_assigns_sequence_without_mutating_ledger_roles() -> None:
    repo = InMemoryConversationRepository()
    msg = build_text_message(
        session_id=SESSION_ID,
        turn_id=uuid4(),
        organization_id=ORG,
        role=MessageRole.USER,
        text="hello",
    )
    stored = repo.append_message(msg)
    assert stored.metadata["sequence"] == 1
    assert stored.role == MessageRole.USER
    assert len(repo.list_messages(SESSION_ID)) == 1
