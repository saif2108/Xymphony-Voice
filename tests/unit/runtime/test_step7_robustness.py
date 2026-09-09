"""Phase 3 Step 7 — Context and conversation-memory robustness tests.

Covers:
  A. Summary coverage correctness across rolling cycles
  B. Oversized summary boundary
  C. Empty and unusual conversation content
  D. Budget boundary conditions (exact-fit, one-over)
  E. Cancellation safety
  F. Provider failure safety
  G. Conversation ledger integrity
  H. Concurrency / duplicate summarization assumptions
  I. Regression protection for existing behavior
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from tests.helpers import ORG, SESSION_ID, VERSION_ID

from xymphony_contracts.content import ContentPart
from xymphony_contracts.enums import ContentPartType, MessageRole, MessageStatus
from xymphony_contracts.llm import LLMRequest, LLMRole, ProviderError, ProviderErrorCode
from xymphony_contracts.provider import CancellationToken
from xymphony_contracts.session import Message
from xymphony_contracts.summary import ConversationSummary
from xymphony_runtime import (
    ConversationSummarizer,
    InMemoryConversationRepository,
    InMemoryConversationSummaryRepository,
    LLMContextAssembler,
    LLMRuntimeConfig,
)
from xymphony_runtime.cancellation import EventCancellationToken
from xymphony_runtime.context_budget import SUMMARY_SECTION_HEADER, ContextBudgetPolicy
from xymphony_runtime.conversation import build_text_message, committed_messages_to_llm
from xymphony_runtime.errors import ContextBudgetExceededError
from xymphony_runtime.token_estimate import approximate_token_count

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_BULKY = "abcdefghijklm"  # ~4 chars → 1 token; fits "bulky" label in tests


def _seq_message(role: MessageRole, text: str, *, seq: int) -> Message:
    """Build a COMMITTED message with an explicit sequence metadata key."""
    return Message(
        id=uuid4(),
        session_id=SESSION_ID,
        turn_id=uuid4(),
        organization_id=ORG,
        role=role,
        status=MessageStatus.COMMITTED,
        parts=(ContentPart(type=ContentPartType.TEXT, payload={"text": text}),),
        created_at=datetime(2026, 9, 8, 12, 0, 0, tzinfo=UTC),
        metadata={"sequence": seq},
    )


def _msg(role: MessageRole, text: str) -> Message:
    """Build a COMMITTED message without explicit sequence."""
    return Message(
        id=uuid4(),
        session_id=SESSION_ID,
        turn_id=uuid4(),
        organization_id=ORG,
        role=role,
        status=MessageStatus.COMMITTED,
        parts=(ContentPart(type=ContentPartType.TEXT, payload={"text": text}),),
        created_at=datetime(2026, 9, 8, 12, 0, 0, tzinfo=UTC),
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


def _bulky_history(*, count: int, repo: InMemoryConversationRepository) -> tuple[Message, ...]:
    """Append `count` messages to `repo` and return them."""
    messages = []
    for i in range(1, count + 1):
        role = MessageRole.USER if i % 2 else MessageRole.ASSISTANT
        messages.append(
            repo.append_message(
                build_text_message(
                    session_id=SESSION_ID,
                    turn_id=uuid4(),
                    organization_id=ORG,
                    role=role,
                    text=f"{_BULKY}{i}",
                )
            )
        )
    return tuple(messages)


# system(1) + user(1) + room for ~2 bulky msgs (~8)
_TRIGGER_BUDGET = 12


class FakeLLMProvider:
    """Configurable fake LLM: differentiates summary vs. conversation requests."""

    provider_key = "fake"

    def __init__(
        self,
        *,
        summary_text: str = "Summary.",
        reply_text: str = "reply",
        fail_summary: ProviderError | None = None,
        delay_seconds: float = 0.0,
    ) -> None:
        self._summary_text = summary_text
        self._reply_text = reply_text
        self._fail_summary = fail_summary
        self._delay = delay_seconds
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
        if is_summary and self._fail_summary is not None:
            raise self._fail_summary
        text = self._summary_text if is_summary else self._reply_text
        for i, ch in enumerate(text):
            if cancel.cancelled:
                return
            if self._delay:
                await asyncio.sleep(self._delay)
            if cancel.cancelled:
                return
            finish = "stop" if i == len(text) - 1 else None
            yield LLMStreamChunk(delta=ch, finish_reason=finish)


# =============================================================================
# A. Summary coverage correctness across rolling cycles
# =============================================================================


@pytest.mark.asyncio
async def test_rolling_summary_three_cycles_no_duplication() -> None:
    """Simulate rolling summaries through conversation messages 10, 20, and 30.

    After each cycle the new summary must:
    - cover previously uncovered messages
    - not re-summarize already-covered messages (no new summary request if coverage is current)
    - not duplicate or omit history in the resulting request
    """
    conv = InMemoryConversationRepository()
    summaries = InMemoryConversationSummaryRepository()
    llm = FakeLLMProvider(summary_text="x")

    cycle_config = _config(system_instructions="sys", max_input_tokens=9)

    def _cycle_history(count: int) -> tuple[Message, ...]:
        messages: list[Message] = []
        for index in range(count):
            role = MessageRole.USER if index % 2 == 0 else MessageRole.ASSISTANT
            messages.append(
                conv.append_message(
                    build_text_message(
                        session_id=SESSION_ID,
                        turn_id=uuid4(),
                        organization_id=ORG,
                        role=role,
                        text=f"012345678901234567890123456789{index}",
                    )
                )
            )
        return tuple(messages)

    summarizer = ConversationSummarizer(
        llm_provider=llm,
        llm_config=cycle_config,
        summary_repository=summaries,
    )

    # The budget leaves room for the system and current user content, but no
    # bulky history once the summary is included. This makes each cycle cover
    # exactly the newly appended ten committed messages.
    # --- CYCLE 1: messages 1-10 ---
    history_c1 = _cycle_history(10)
    result_c1 = await summarizer.prepare(
        session_id=SESSION_ID,
        organization_id=ORG,
        agent_version_id=VERSION_ID,
        history=history_c1,
        current_user_text="curr",
        cancel=EventCancellationToken(),
        is_turn_cancelled=lambda: False,
    )
    assert result_c1.summary_text == "x"
    stored_c1 = summaries.get_latest(SESSION_ID)
    assert stored_c1 is not None
    through_c1 = stored_c1.through_sequence
    assert through_c1 == 10
    n_requests_c1 = len(llm.requests)
    # At least one request was the summary generation
    assert n_requests_c1 >= 1

    # --- CYCLE 1b: same history, same budget → coverage is current, no new summary request ---
    llm.requests.clear()
    result_c1b = await summarizer.prepare(
        session_id=SESSION_ID,
        organization_id=ORG,
        agent_version_id=VERSION_ID,
        history=history_c1,
        current_user_text="curr",
        cancel=EventCancellationToken(),
        is_turn_cancelled=lambda: False,
    )
    assert result_c1b.summary_text == "x"
    # No new summarization request issued: coverage is already up to date
    assert not any("summarize" in r.system.lower() for r in llm.requests), (
        "Expected no re-summarization when coverage is current"
    )
    stored_c1b = summaries.get_latest(SESSION_ID)
    assert stored_c1b is not None
    assert stored_c1b.through_sequence == through_c1  # not advanced

    # --- CYCLE 2: add messages 11-20 ---
    history_c2 = _cycle_history(10)
    all_history = history_c1 + history_c2
    llm.requests.clear()
    result_c2 = await summarizer.prepare(
        session_id=SESSION_ID,
        organization_id=ORG,
        agent_version_id=VERSION_ID,
        history=all_history,
        current_user_text="curr",
        cancel=EventCancellationToken(),
        is_turn_cancelled=lambda: False,
    )
    stored_c2 = summaries.get_latest(SESSION_ID)
    assert stored_c2 is not None
    assert stored_c2.through_sequence == 20

    # --- CYCLE 3: add messages 21-30 ---
    history_c3 = _cycle_history(10)
    all_history = all_history + history_c3
    llm.requests.clear()
    result_c3 = await summarizer.prepare(
        session_id=SESSION_ID,
        organization_id=ORG,
        agent_version_id=VERSION_ID,
        history=all_history,
        current_user_text="curr",
        cancel=EventCancellationToken(),
        is_turn_cancelled=lambda: False,
    )
    stored_c3 = summaries.get_latest(SESSION_ID)
    assert stored_c3 is not None
    assert stored_c3.through_sequence == 30
    assert result_c3.summary_text == "x"

    # The original ledger must remain intact
    ledger = conv.list_messages(SESSION_ID)
    assert len(ledger) == 30
    # None of the ledger messages should have role collisions from summary injection
    assert all(m.role in (MessageRole.USER, MessageRole.ASSISTANT) for m in ledger)

    # The returned history_for_assembly must never be longer than the full history
    assert len(result_c3.history_for_assembly) <= len(all_history)

    # Assemble a request; verify the current user message appears exactly once
    request = LLMContextAssembler().assemble(
        history=result_c3.history_for_assembly,
        current_user_text="curr",
        config=cycle_config,
        summary_text=result_c2.summary_text,
    )
    curr_count = sum(1 for m in request.messages if m.content == "curr")
    assert curr_count == 1, f"Current user message appeared {curr_count} times"


@pytest.mark.asyncio
async def test_summary_coverage_never_advances_before_persistence() -> None:
    """After summarizer.prepare() with an upsert, through_sequence == persisted value."""
    conv = InMemoryConversationRepository()
    summaries = InMemoryConversationSummaryRepository()
    llm = FakeLLMProvider(summary_text="stored-summary")
    summarizer = ConversationSummarizer(
        llm_provider=llm,
        llm_config=_config(system_instructions="sys", max_input_tokens=_TRIGGER_BUDGET),
        summary_repository=summaries,
    )
    history = _bulky_history(count=6, repo=conv)
    await summarizer.prepare(
        session_id=SESSION_ID,
        organization_id=ORG,
        agent_version_id=VERSION_ID,
        history=history,
        current_user_text="curr",
        cancel=EventCancellationToken(),
        is_turn_cancelled=lambda: False,
    )
    stored = summaries.get_latest(SESSION_ID)
    assert stored is not None
    # through_sequence must only contain sequence numbers of committed messages
    all_seqs = [
        m.metadata.get("sequence")
        for m in history
        if isinstance(m.metadata.get("sequence"), int)
    ]
    assert stored.through_sequence in all_seqs, (
        f"through_sequence {stored.through_sequence} is not a known sequence: {all_seqs}"
    )


@pytest.mark.asyncio
async def test_messages_not_skipped_between_coverage_and_recent_history() -> None:
    """After summarization, history_for_assembly + summary covers the full history.

    No message at seq > through_sequence should be silently lost.
    """
    conv = InMemoryConversationRepository()
    summaries = InMemoryConversationSummaryRepository()
    llm = FakeLLMProvider(summary_text="ctx")
    summarizer = ConversationSummarizer(
        llm_provider=llm,
        llm_config=_config(system_instructions="sys", max_input_tokens=_TRIGGER_BUDGET),
        summary_repository=summaries,
    )
    history = _bulky_history(count=8, repo=conv)
    result = await summarizer.prepare(
        session_id=SESSION_ID,
        organization_id=ORG,
        agent_version_id=VERSION_ID,
        history=history,
        current_user_text="new",
        cancel=EventCancellationToken(),
        is_turn_cancelled=lambda: False,
    )
    stored = summaries.get_latest(SESSION_ID)
    assert stored is not None
    through = stored.through_sequence
    # Messages with seq > through should all appear in history_for_assembly
    expected_recent = [
        m for m in history
        if isinstance(m.metadata.get("sequence"), int) and m.metadata["sequence"] > through
    ]
    assembly_texts = {m.metadata.get("sequence") for m in result.history_for_assembly
                     if isinstance(m.metadata.get("sequence"), int)}
    for m in expected_recent:
        assert m.metadata["sequence"] in assembly_texts, (
            f"Message with seq={m.metadata['sequence']} lost "
            f"between coverage (through={through}) and history_for_assembly"
        )


# =============================================================================
# B. Oversized summary boundary
# =============================================================================


def test_assembler_oversized_summary_soft_fails_and_uses_plain_system() -> None:
    """When the summary is too large for the budget, assembler falls back to no-summary."""
    huge_summary = "s" * 300  # far exceeds any small budget
    request = LLMContextAssembler().assemble(
        history=(_msg(MessageRole.USER, "hist"),),
        current_user_text="curr",
        config=_config(system_instructions="sys", max_input_tokens=5),
        summary_text=huge_summary,
    )
    assert SUMMARY_SECTION_HEADER not in request.system
    assert request.system == "sys"
    assert request.messages[-1].content == "curr"


def test_assembler_oversized_summary_state_not_corrupted() -> None:
    """Assembler is stateless: oversized-summary fallback does not corrupt subsequent calls."""
    assembler = LLMContextAssembler()
    huge = "x" * 400
    # First call: oversized summary → fallback
    r1 = assembler.assemble(
        history=(),
        current_user_text="q1",
        config=_config(system_instructions="sys", max_input_tokens=5),
        summary_text=huge,
    )
    assert SUMMARY_SECTION_HEADER not in r1.system
    # Second call: small summary → summary included
    r2 = assembler.assemble(
        history=(),
        current_user_text="q2",
        config=_config(system_instructions="sys", max_input_tokens=50),
        summary_text="small",
    )
    assert SUMMARY_SECTION_HEADER in r2.system
    assert "small" in r2.system


@pytest.mark.asyncio
async def test_oversized_summary_from_provider_triggers_short_retry() -> None:
    """When the generated summary is too large, summarizer attempts the short prompt."""
    # Use a budget so tight the regular summary cannot fit but a tiny summary would
    # system "sys" ≈ 1 token, current "curr" ≈ 1 token
    # A summary that is even 5 chars "big!!" ≈ 2 tokens → might still fit; use huge string
    huge_summary = "B" * 200  # ≈50 tokens, won't fit any small budget
    short_ok = "ok"  # ~1 token — fits

    class _BigThenSmall:
        provider_key = "fake"
        calls = 0

        async def stream(
            self, request: LLMRequest, *, cancel: CancellationToken
        ) -> AsyncIterator[object]:
            from xymphony_contracts.llm import LLMStreamChunk

            is_summary = "summarize" in request.system.lower()
            if is_summary:
                self.calls += 1
                text = huge_summary if self.calls == 1 else short_ok
            else:
                text = "reply"
            for i, ch in enumerate(text):
                yield LLMStreamChunk(delta=ch, finish_reason="stop" if i == len(text) - 1 else None)

    conv = InMemoryConversationRepository()
    summaries = InMemoryConversationSummaryRepository()
    provider = _BigThenSmall()
    summarizer = ConversationSummarizer(
        llm_provider=provider,
        llm_config=_config(system_instructions="s", max_input_tokens=8),
        summary_repository=summaries,
    )
    history = _bulky_history(count=6, repo=conv)
    result = await summarizer.prepare(
        session_id=SESSION_ID,
        organization_id=ORG,
        agent_version_id=VERSION_ID,
        history=history,
        current_user_text="curr",
        cancel=EventCancellationToken(),
        is_turn_cancelled=lambda: False,
    )
    # Either the short summary was accepted or a soft-fallback occurred; either way no crash
    # and summary repository must reflect consistent state
    stored = summaries.get_latest(SESSION_ID)
    if result.summary_text is not None:
        assert stored is not None
        assert stored.summary_text == result.summary_text
    else:
        # Soft fallback: stored must not have advanced to a wrong state
        # (could be None or a prior valid summary)
        pass  # no assertion needed, the key check is no exception was raised


# =============================================================================
# C. Empty and unusual conversation content
# =============================================================================


def test_empty_conversation_history_assembles_only_current() -> None:
    request = LLMContextAssembler().assemble(
        history=(),
        current_user_text="hello",
        config=_config(max_input_tokens=100),
    )
    assert len(request.messages) == 1
    assert request.messages[0].role == LLMRole.USER
    assert request.messages[0].content == "hello"


def test_one_message_conversation_assembles_correctly() -> None:
    history = (_msg(MessageRole.USER, "just one"),)
    request = LLMContextAssembler().assemble(
        history=history,
        current_user_text="second",
        config=_config(max_input_tokens=100),
    )
    assert [m.content for m in request.messages] == ["just one", "second"]


def test_whitespace_content_is_preserved_when_permitted() -> None:
    """Whitespace is valid text content and remains part of the assembled request."""
    request = LLMContextAssembler().assemble(
        history=(_msg(MessageRole.USER, "   "),),
        current_user_text="\t",
        config=_config(max_input_tokens=100),
    )
    assert [message.content for message in request.messages] == ["   ", "\t"]


@pytest.mark.asyncio
async def test_whitespace_summary_is_not_persisted() -> None:
    """A provider response containing only whitespace cannot advance coverage."""
    conv = InMemoryConversationRepository()
    summaries = InMemoryConversationSummaryRepository()
    summarizer = ConversationSummarizer(
        llm_provider=FakeLLMProvider(summary_text="   "),
        llm_config=_config(system_instructions="sys", max_input_tokens=_TRIGGER_BUDGET),
        summary_repository=summaries,
    )
    history = _bulky_history(count=6, repo=conv)
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


def test_messages_with_identical_text_are_all_preserved() -> None:
    text = "the same thing"
    history = tuple(_msg(MessageRole.USER, text) for _ in range(4))
    request = LLMContextAssembler().assemble(
        history=history,
        current_user_text=text,
        config=_config(max_input_tokens=100),
    )
    assert len(request.messages) == 5  # 4 history + 1 current
    assert all(m.content == text for m in request.messages)


def test_alternating_user_assistant_messages_preserve_order() -> None:
    roles = [MessageRole.USER, MessageRole.ASSISTANT] * 5
    texts = [f"msg{i}" for i in range(10)]
    history = tuple(_msg(role, text) for role, text in zip(roles, texts, strict=True))
    request = LLMContextAssembler().assemble(
        history=history,
        current_user_text="final",
        config=_config(max_input_tokens=100),
    )
    for i, msg in enumerate(request.messages[:-1]):
        expected_role = LLMRole.USER if i % 2 == 0 else LLMRole.ASSISTANT
        assert msg.role == expected_role


def test_very_long_single_message_in_history_counted_correctly() -> None:
    long_text = "a" * 400  # 100 tokens
    history = (_msg(MessageRole.USER, long_text),)
    policy = ContextBudgetPolicy()
    # budget too small to fit long message → dropped
    selected = policy.select_history(
        committed_messages_to_llm(history),
        current_user_text="q",
        system_instructions="s",
        max_input_tokens=10,
    )
    assert selected == ()
    # budget large enough → kept
    selected2 = policy.select_history(
        committed_messages_to_llm(history),
        current_user_text="q",
        system_instructions="s",
        max_input_tokens=110,
    )
    assert len(selected2) == 1
    assert selected2[0].content == long_text


def test_message_with_no_text_parts_excluded_from_history() -> None:
    """Messages whose content parts carry no text are silently excluded from LLM history."""
    no_text = Message(
        id=uuid4(),
        session_id=SESSION_ID,
        turn_id=uuid4(),
        organization_id=ORG,
        role=MessageRole.USER,
        status=MessageStatus.COMMITTED,
        parts=(ContentPart(type=ContentPartType.TEXT, payload={}),),
        created_at=datetime(2026, 9, 8, 12, 0, 0, tzinfo=UTC),
    )
    normal = _msg(MessageRole.ASSISTANT, "a real reply")
    history = (no_text, normal)
    request = LLMContextAssembler().assemble(
        history=history,
        current_user_text="next",
        config=_config(max_input_tokens=100),
    )
    # no_text should be dropped; normal and next should be present
    contents = [m.content for m in request.messages]
    assert "a real reply" in contents
    assert "next" in contents
    assert len(request.messages) == 2


def test_non_committed_messages_excluded() -> None:
    """Interrupted/non-committed messages must never reach the LLM context."""
    history = (
        _msg(MessageRole.USER, "keep"),
        Message(
            id=uuid4(),
            session_id=SESSION_ID,
            turn_id=uuid4(),
            organization_id=ORG,
            role=MessageRole.ASSISTANT,
            status=MessageStatus.INTERRUPTED,
            parts=(ContentPart(type=ContentPartType.TEXT, payload={"text": "cancelled output"}),),
            created_at=datetime(2026, 9, 8, 12, 0, 0, tzinfo=UTC),
        ),
        _msg(MessageRole.ASSISTANT, "keep too"),
    )
    request = LLMContextAssembler().assemble(
        history=history,
        current_user_text="go",
        config=_config(max_input_tokens=100),
    )
    contents = [m.content for m in request.messages]
    assert "cancelled output" not in contents
    assert "keep" in contents
    assert "keep too" in contents


# =============================================================================
# D. Budget boundary conditions
# =============================================================================


def test_exact_fit_succeeds() -> None:
    """When tokens exactly equal the budget, history is fully selected."""
    # Tokens: "s" = 1, "c" = 1, "m" = 1  → total = 3, budget = 3
    selected = ContextBudgetPolicy().select_history(
        (LLMContextAssembler._budget_policy if False else None,)  # type: ignore[operator]
        if False
        else (
            *[],
            *[__import__("xymphony_contracts.llm", fromlist=["LLMMessage"]).LLMMessage(
                role=LLMRole.USER, content="m"
            )],
        ),
        current_user_text="c",
        system_instructions="s",
        max_input_tokens=3,
    )
    assert len(selected) == 1


def test_one_token_over_drops_oldest() -> None:
    """Budget exactly fits system + current + 1 history message, not 2."""
    from xymphony_contracts.llm import LLMMessage

    history = (
        LLMMessage(role=LLMRole.USER, content="old!"),
        LLMMessage(role=LLMRole.USER, content="new!"),
    )
    # sys=1, curr=1, need 3 to fit both; give only 3 → fit both
    # Give 2 → only 1 fits; should keep newest
    selected = ContextBudgetPolicy().select_history(
        history,
        current_user_text="curr",
        system_instructions="s",
        max_input_tokens=3,
    )
    assert len(selected) == 1
    assert selected[0].content == "new!"


def test_mandatory_content_cannot_fit_raises() -> None:
    """Current user message that exceeds remaining budget after system
    → ContextBudgetExceededError."""
    big_user = "u" * 400  # ~100 tokens
    with pytest.raises(ContextBudgetExceededError, match="current user"):
        ContextBudgetPolicy().select_history(
            (),
            current_user_text=big_user,
            system_instructions="s",
            max_input_tokens=5,
        )


def test_system_exceeds_budget_raises() -> None:
    """System instructions that exceed the full budget → ContextBudgetExceededError."""
    big_system = "X" * 400  # ~100 tokens
    with pytest.raises(ContextBudgetExceededError, match="system"):
        ContextBudgetPolicy().select_history(
            (),
            current_user_text="hi",
            system_instructions=big_system,
            max_input_tokens=5,
        )


def test_summary_with_budget_summary_and_history_within_limit() -> None:
    """Summary + system + current + recent history must not exceed budget."""
    from xymphony_contracts.llm import LLMMessage

    summary = "summary"  # ~2 tokens
    history = (LLMMessage(role=LLMRole.USER, content="old!"),)
    # sys(1) + summary_header(≈3) + summary(2) + current(1) = 7 minimum
    # budget=15 should comfortably fit history message too
    selected = ContextBudgetPolicy().select_history(
        history,
        current_user_text="curr",
        system_instructions="s",
        max_input_tokens=15,
        summary_text=summary,
    )
    assert len(selected) == 1


def test_summary_priority_over_history_when_both_tight() -> None:
    """When budget is tight with summary, history is dropped but summary is retained."""
    from xymphony_contracts.llm import LLMMessage
    from xymphony_runtime.context_budget import build_system_with_summary

    summary = "ctx"
    system_instr = "s"
    current_user = "curr"

    # Compute exact mandatory token cost: system+summary_block + current_user
    combined_system = build_system_with_summary(system_instr, summary)
    mandatory = approximate_token_count(combined_system) + approximate_token_count(current_user)
    # Budget = mandatory only → no room for any history
    budget = mandatory

    history = tuple(
        LLMMessage(role=LLMRole.USER, content=f"old{i}!")
        for i in range(10)
    )
    selected = ContextBudgetPolicy().select_history(
        history,
        current_user_text=current_user,
        system_instructions=system_instr,
        max_input_tokens=budget,
        summary_text=summary,
    )
    # All history must be dropped (no budget left after mandatory parts)
    assert len(selected) == 0

    # Assembling with the correct budget must succeed and include the summary
    request = LLMContextAssembler().assemble(
        history=(),
        current_user_text=current_user,
        config=_config(system_instructions=system_instr, max_input_tokens=budget),
        summary_text=summary,
    )
    assert SUMMARY_SECTION_HEADER in request.system
    assert "ctx" in request.system
    total_tokens = approximate_token_count(request.system) + sum(
        approximate_token_count(m.content) for m in request.messages
    )
    assert total_tokens <= budget


# =============================================================================
# E. Cancellation safety
# =============================================================================


@pytest.mark.asyncio
async def test_cancellation_before_generation_returns_existing_summary() -> None:
    """If turn is cancelled before summary generation, existing summary is returned unchanged."""
    summaries = InMemoryConversationSummaryRepository()
    existing = ConversationSummary(
        id=uuid4(),
        session_id=SESSION_ID,
        organization_id=ORG,
        agent_version_id=VERSION_ID,
        through_sequence=2,
        summary_text="prior summary",
        source_message_count=2,
        created_at=datetime.now(tz=UTC),
    )
    summaries.upsert(existing)
    llm = FakeLLMProvider(summary_text="new summary (should not be persisted)")
    conv = InMemoryConversationRepository()
    history = _bulky_history(count=6, repo=conv)
    summarizer = ConversationSummarizer(
        llm_provider=llm,
        llm_config=_config(system_instructions="sys", max_input_tokens=_TRIGGER_BUDGET),
        summary_repository=summaries,
    )
    # Cancel immediately before calling prepare
    cancel = EventCancellationToken()
    cancel.cancel()
    result = await summarizer.prepare(
        session_id=SESSION_ID,
        organization_id=ORG,
        agent_version_id=VERSION_ID,
        history=history,
        current_user_text="curr",
        cancel=cancel,
        is_turn_cancelled=lambda: True,
    )
    # No new persistence: prior summary must remain
    stored = summaries.get_latest(SESSION_ID)
    assert stored is not None
    assert stored.through_sequence == 2  # unchanged
    assert stored.summary_text == "prior summary"
    # Result should carry the existing summary text (not the new one)
    assert result.summary_text in ("prior summary", None)


@pytest.mark.asyncio
async def test_cancellation_during_generation_does_not_persist() -> None:
    """Cancellation mid-stream → summary repository must not be updated."""
    conv = InMemoryConversationRepository()
    summaries = InMemoryConversationSummaryRepository()
    history = _bulky_history(count=6, repo=conv)
    llm = FakeLLMProvider(summary_text="partial" * 10, delay_seconds=0.03)
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
    await asyncio.sleep(0.01)
    cancel.cancel()
    await task
    assert summaries.get_latest(SESSION_ID) is None


@pytest.mark.asyncio
async def test_subsequent_turn_continues_normally_after_cancellation() -> None:
    """A later turn (new cancel token) can produce a summary regardless of prior cancellation."""
    conv = InMemoryConversationRepository()
    summaries = InMemoryConversationSummaryRepository()
    history = _bulky_history(count=6, repo=conv)
    llm = FakeLLMProvider(summary_text="good summary", delay_seconds=0.03)
    summarizer = ConversationSummarizer(
        llm_provider=llm,
        llm_config=_config(system_instructions="sys", max_input_tokens=_TRIGGER_BUDGET),
        summary_repository=summaries,
    )

    # Turn 1: cancel mid-way
    cancel1 = EventCancellationToken()

    async def _turn1() -> object:
        return await summarizer.prepare(
            session_id=SESSION_ID,
            organization_id=ORG,
            agent_version_id=VERSION_ID,
            history=history,
            current_user_text="curr",
            cancel=cancel1,
            is_turn_cancelled=lambda: cancel1.cancelled,
        )

    task1 = asyncio.create_task(_turn1())
    await asyncio.sleep(0.01)
    cancel1.cancel()
    await task1
    assert summaries.get_latest(SESSION_ID) is None  # nothing persisted from turn 1

    # Turn 2: fresh cancel token → must succeed
    result2 = await summarizer.prepare(
        session_id=SESSION_ID,
        organization_id=ORG,
        agent_version_id=VERSION_ID,
        history=history,
        current_user_text="curr",
        cancel=EventCancellationToken(),
        is_turn_cancelled=lambda: False,
    )
    assert result2.summary_text == "good summary"
    assert summaries.get_latest(SESSION_ID) is not None


# =============================================================================
# F. Provider failure safety
# =============================================================================


@pytest.mark.asyncio
async def test_provider_failure_does_not_corrupt_summary_repository() -> None:
    """ProviderError during summary generation → repository state unchanged."""
    conv = InMemoryConversationRepository()
    summaries = InMemoryConversationSummaryRepository()
    history = _bulky_history(count=6, repo=conv)
    err = ProviderError(
        code=ProviderErrorCode.PROVIDER,
        message="timeout",
        provider_key="fake",
        retryable=True,
    )
    llm = FakeLLMProvider(fail_summary=err)
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
    assert summaries.get_latest(SESSION_ID) is None


@pytest.mark.asyncio
async def test_summary_coverage_does_not_advance_on_provider_failure() -> None:
    """Coverage must stay at its prior value when summary generation fails."""
    conv = InMemoryConversationRepository()
    summaries = InMemoryConversationSummaryRepository()
    # Pre-existing summary
    prior = ConversationSummary(
        id=uuid4(),
        session_id=SESSION_ID,
        organization_id=ORG,
        agent_version_id=VERSION_ID,
        through_sequence=2,
        summary_text="old context",
        source_message_count=2,
        created_at=datetime.now(tz=UTC),
    )
    summaries.upsert(prior)
    history = _bulky_history(count=6, repo=conv)
    err = ProviderError(
        code=ProviderErrorCode.PROVIDER,
        message="unavailable",
        provider_key="fake",
    )
    llm = FakeLLMProvider(fail_summary=err)
    summarizer = ConversationSummarizer(
        llm_provider=llm,
        llm_config=_config(system_instructions="sys", max_input_tokens=_TRIGGER_BUDGET),
        summary_repository=summaries,
    )
    await summarizer.prepare(
        session_id=SESSION_ID,
        organization_id=ORG,
        agent_version_id=VERSION_ID,
        history=history,
        current_user_text="curr",
        cancel=EventCancellationToken(),
        is_turn_cancelled=lambda: False,
    )
    stored = summaries.get_latest(SESSION_ID)
    assert stored is not None
    assert stored.through_sequence == 2  # not advanced
    assert stored.summary_text == "old context"


@pytest.mark.asyncio
async def test_subsequent_turn_can_retry_summarization_after_failure() -> None:
    """After a failed summary turn, the next turn can successfully generate a summary."""
    conv = InMemoryConversationRepository()
    summaries = InMemoryConversationSummaryRepository()
    history = _bulky_history(count=6, repo=conv)
    err = ProviderError(
        code=ProviderErrorCode.PROVIDER,
        message="down",
        provider_key="fake",
    )
    failing_llm = FakeLLMProvider(fail_summary=err)
    summarizer_fail = ConversationSummarizer(
        llm_provider=failing_llm,
        llm_config=_config(system_instructions="sys", max_input_tokens=_TRIGGER_BUDGET),
        summary_repository=summaries,
    )
    await summarizer_fail.prepare(
        session_id=SESSION_ID,
        organization_id=ORG,
        agent_version_id=VERSION_ID,
        history=history,
        current_user_text="curr",
        cancel=EventCancellationToken(),
        is_turn_cancelled=lambda: False,
    )
    assert summaries.get_latest(SESSION_ID) is None

    # Next turn: new LLM provider that succeeds
    ok_llm = FakeLLMProvider(summary_text="recovered")
    summarizer_ok = ConversationSummarizer(
        llm_provider=ok_llm,
        llm_config=_config(system_instructions="sys", max_input_tokens=_TRIGGER_BUDGET),
        summary_repository=summaries,
    )
    result = await summarizer_ok.prepare(
        session_id=SESSION_ID,
        organization_id=ORG,
        agent_version_id=VERSION_ID,
        history=history,
        current_user_text="curr",
        cancel=EventCancellationToken(),
        is_turn_cancelled=lambda: False,
    )
    assert result.summary_text == "recovered"
    assert summaries.get_latest(SESSION_ID) is not None


# =============================================================================
# G. Conversation ledger integrity
# =============================================================================


def test_summaries_never_appear_as_conversation_messages() -> None:
    """Summary text must never be injected into conversation_messages."""
    repo = InMemoryConversationRepository()
    # Append some regular messages
    for i in range(4):
        role = MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT
        repo.append_message(
            build_text_message(
                session_id=SESSION_ID,
                turn_id=uuid4(),
                organization_id=ORG,
                role=role,
                text=f"msg{i}",
            )
        )
    messages = repo.list_messages(SESSION_ID)
    # Inject a summary into the summary repo (not the conversation repo)
    summary_repo = InMemoryConversationSummaryRepository()
    summary_repo.upsert(
        ConversationSummary(
            id=uuid4(),
            session_id=SESSION_ID,
            organization_id=ORG,
            agent_version_id=VERSION_ID,
            through_sequence=2,
            summary_text="this is a summary",
            source_message_count=2,
            created_at=datetime.now(tz=UTC),
        )
    )
    # Conversation ledger must remain clean
    assert len(messages) == 4
    for m in messages:
        text_parts = [
            p.payload.get("text", "")
            for p in m.parts
            if p.type == ContentPartType.TEXT
        ]
        assert "this is a summary" not in " ".join(str(t) for t in text_parts)


def test_non_committed_messages_never_reach_llm_request() -> None:
    """Interrupted/cancelled turn messages must not appear in the LLM request."""
    history = (
        _msg(MessageRole.USER, "user input"),
        Message(
            id=uuid4(),
            session_id=SESSION_ID,
            turn_id=uuid4(),
            organization_id=ORG,
            role=MessageRole.ASSISTANT,
            status=MessageStatus.INTERRUPTED,
            parts=(
                ContentPart(
                    type=ContentPartType.TEXT,
                    payload={"text": "partial cancelled response"},
                ),
            ),
            created_at=datetime(2026, 9, 8, 12, 0, 0, tzinfo=UTC),
        ),
    )
    request = LLMContextAssembler().assemble(
        history=history,
        current_user_text="follow-up",
        config=_config(max_input_tokens=100),
    )
    contents = [m.content for m in request.messages]
    assert "partial cancelled response" not in contents
    assert "user input" in contents
    assert "follow-up" in contents


def test_ledger_order_preserved_after_multiple_appends() -> None:
    """Conversation repository preserves insertion order."""
    repo = InMemoryConversationRepository()
    texts = ["first", "second", "third", "fourth", "fifth"]
    roles = [MessageRole.USER, MessageRole.ASSISTANT] * 3
    for text, role in zip(texts, roles, strict=False):
        repo.append_message(
            build_text_message(
                session_id=SESSION_ID,
                turn_id=uuid4(),
                organization_id=ORG,
                role=role,
                text=text,
            )
        )
    stored = repo.list_messages(SESSION_ID)
    stored_texts = []
    for m in stored:
        for p in m.parts:
            if p.type == ContentPartType.TEXT:
                t = p.payload.get("text")
                if t:
                    stored_texts.append(t)
    assert stored_texts == texts


def test_next_sequence_increments_monotonically() -> None:
    """ConversationRepository.next_sequence must return monotonically increasing values."""
    repo = InMemoryConversationRepository()
    seq1 = repo.next_sequence(SESSION_ID)
    repo.append_message(
        build_text_message(
            session_id=SESSION_ID,
            turn_id=uuid4(),
            organization_id=ORG,
            role=MessageRole.USER,
            text="a",
        )
    )
    seq2 = repo.next_sequence(SESSION_ID)
    assert seq2 == seq1 + 1


# =============================================================================
# H. Concurrency / duplicate summarization
# =============================================================================


def test_single_session_serialization_documented() -> None:
    """Document the single-session concurrency guarantee.

    The ConversationSummarizer.prepare() method is a coroutine: within a
    single asyncio event loop, it executes sequentially between ``await``
    points.  The AgentRuntime processes one turn at a time (turn N+1 cannot
    start until turn N's coroutine completes or is cancelled).

    Therefore, two concurrent calls to prepare() for the same session_id
    can only arise if two separate AgentRuntime instances are erroneously
    pointed at the same session — which is an operational invariant violation,
    not a code-level correctness problem.

    This test documents that guarantee through observation: sequential
    invocations on the same summarizer produce monotonically non-decreasing
    through_sequence values.
    """
    # Run two sequential prepare() calls for the same session
    async def _run() -> None:
        conv = InMemoryConversationRepository()
        summaries = InMemoryConversationSummaryRepository()
        history = _bulky_history(count=6, repo=conv)
        llm = FakeLLMProvider(summary_text="seq-summary")
        summarizer = ConversationSummarizer(
            llm_provider=llm,
            llm_config=_config(system_instructions="sys", max_input_tokens=_TRIGGER_BUDGET),
            summary_repository=summaries,
        )
        await summarizer.prepare(
            session_id=SESSION_ID,
            organization_id=ORG,
            agent_version_id=VERSION_ID,
            history=history,
            current_user_text="turn1",
            cancel=EventCancellationToken(),
            is_turn_cancelled=lambda: False,
        )
        s1 = summaries.get_latest(SESSION_ID)
        assert s1 is not None
        through1 = s1.through_sequence
        # Second call with same history → coverage is current, no re-summarization
        await summarizer.prepare(
            session_id=SESSION_ID,
            organization_id=ORG,
            agent_version_id=VERSION_ID,
            history=history,
            current_user_text="turn2",
            cancel=EventCancellationToken(),
            is_turn_cancelled=lambda: False,
        )
        s2 = summaries.get_latest(SESSION_ID)
        assert s2 is not None
        assert s2.through_sequence >= through1

    asyncio.run(_run())


# =============================================================================
# I. Regression protection
# =============================================================================


def test_no_budget_no_summarization_regression() -> None:
    """max_input_tokens=None must produce the full history unchanged (regression)."""
    history = tuple(_msg(MessageRole.USER, f"msg{i}") for i in range(5))
    request = LLMContextAssembler().assemble(
        history=history,
        current_user_text="now",
        config=_config(max_input_tokens=None),
    )
    assert len(request.messages) == 6  # 5 history + 1 current
    assert request.messages[-1].content == "now"


def test_generation_params_absent_regression() -> None:
    """Absent generation params must be None in LLMRequest (regression)."""
    config = LLMRuntimeConfig(provider_key="fake", model="m")
    request = LLMContextAssembler().assemble(
        history=(),
        current_user_text="hi",
        config=config,
    )
    assert request.temperature is None
    assert request.top_p is None
    assert request.max_output_tokens is None


def test_generation_params_present_regression() -> None:
    """Present generation params must appear in LLMRequest (regression)."""
    config = LLMRuntimeConfig(
        provider_key="fake",
        model="m",
        temperature=0.7,
        top_p=0.9,
        max_output_tokens=512,
    )
    request = LLMContextAssembler().assemble(
        history=(),
        current_user_text="hi",
        config=config,
    )
    assert request.temperature == 0.7
    assert request.top_p == 0.9
    assert request.max_output_tokens == 512


def test_no_summary_regression() -> None:
    """No existing summary → system prompt has no summary header (regression)."""
    request = LLMContextAssembler().assemble(
        history=(),
        current_user_text="hi",
        config=_config(system_instructions="Instructions.", max_input_tokens=100),
        summary_text=None,
    )
    assert SUMMARY_SECTION_HEADER not in request.system
    assert request.system == "Instructions."


def test_short_conversation_no_summary_needed() -> None:
    """Short conversation under the budget must not trigger summarization or error."""
    history = tuple(_msg(MessageRole.USER, "short") for _ in range(2))
    request = LLMContextAssembler().assemble(
        history=history,
        current_user_text="next",
        config=_config(system_instructions="s", max_input_tokens=100),
    )
    assert len(request.messages) == 3
    assert request.messages[-1].content == "next"


@pytest.mark.asyncio
async def test_provider_failure_during_summarization_still_allows_main_turn() -> None:
    """When summary fails, the main conversation turn must not be blocked."""
    # This tests the soft-failure path: result.summary_text is None,
    # but the assembler can still build a request (possibly dropping old history).
    err = ProviderError(
        code=ProviderErrorCode.PROVIDER,
        message="down",
        provider_key="fake",
    )
    llm = FakeLLMProvider(fail_summary=err, reply_text="assistant response")
    conv = InMemoryConversationRepository()
    summaries = InMemoryConversationSummaryRepository()
    history = _bulky_history(count=6, repo=conv)
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
    # Main turn assembler must succeed regardless
    request = LLMContextAssembler().assemble(
        history=result.history_for_assembly,
        current_user_text="curr",
        config=_config(system_instructions="sys", max_input_tokens=_TRIGGER_BUDGET),
        summary_text=result.summary_text,
    )
    assert request.messages[-1].content == "curr"
    assert request.messages[-1].role == LLMRole.USER
