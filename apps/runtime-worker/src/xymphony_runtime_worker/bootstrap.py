"""Voice worker bootstrap — wires session, providers, runtime, and bridge."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from pydantic import JsonValue
from sqlalchemy.orm import Session as SqlSession

from xymphony_api.mapping import version_to_contract
from xymphony_api.persistence.postgres import (
    PostgresConversationRepository,
    PostgresConversationSummaryRepository,
    PostgresSessionRepository,
)
from xymphony_api.repositories import AgentVersionRepository
from xymphony_api.repositories import ConversationRepository as SqlConversationRepository
from xymphony_api.repositories import ConversationSummaryRepository as SqlSummaryRepository
from xymphony_api.repositories import SessionRepository as SqlSessionRepository
from xymphony_contracts import AgentVersion
from xymphony_contracts.llm import LLMProvider
from xymphony_contracts.media_transport import MediaTransport
from xymphony_contracts.persistence import (
    ConversationRepository,
    ConversationSummaryRepository,
    CreateSessionRequest,
    SessionRepository,
)
from xymphony_contracts.session import Message
from xymphony_contracts.session import Session as SessionContract
from xymphony_contracts.stt import STTProvider
from xymphony_contracts.summary import ConversationSummary
from xymphony_contracts.tts import TTSOutputAudioResolver, TTSProvider
from xymphony_providers.registry import (
    create_llm_provider,
    create_stt_provider,
    create_tts_provider,
    normalize_llm_provider_key,
)
from xymphony_realtime import LiveKitMediaTransport
from xymphony_runtime import (
    AgentRuntime,
    LLMRuntimeConfig,
    RuntimeContext,
    RuntimeMediaBridge,
    STTRuntimeConfig,
    TTSRuntimeConfig,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VoiceWorkerComponents:
    bridge: RuntimeMediaBridge
    runtime: AgentRuntime
    session: SessionContract
    agent_version: AgentVersion


class _CommittingSessionRepository:
    """Wraps a session repository and commits after each write."""

    def __init__(self, inner: SessionRepository, sql: SqlSession) -> None:
        self._inner = inner
        self._sql = sql

    def create_session(self, request: CreateSessionRequest) -> SessionContract:
        result = self._inner.create_session(request)
        self._sql.commit()
        return result

    def get_session(
        self,
        session_id: UUID,
        *,
        organization_id: UUID | None = None,
        project_id: UUID | None = None,
    ) -> SessionContract | None:
        return self._inner.get_session(
            session_id,
            organization_id=organization_id,
            project_id=project_id,
        )

    def update_session(self, session: SessionContract) -> SessionContract:
        result = self._inner.update_session(session)
        self._sql.commit()
        return result


class _CommittingConversationRepository:
    """Wraps a conversation repository and commits after each write."""

    def __init__(self, inner: ConversationRepository, sql: SqlSession) -> None:
        self._inner = inner
        self._sql = sql

    def append_message(self, message: Message) -> Message:
        result = self._inner.append_message(message)
        self._sql.commit()
        return result

    def list_messages(
        self,
        session_id: UUID,
        *,
        organization_id: UUID | None = None,
    ) -> tuple[Message, ...]:
        return self._inner.list_messages(session_id, organization_id=organization_id)

    def next_sequence(self, session_id: UUID) -> int:
        return self._inner.next_sequence(session_id)


class _CommittingConversationSummaryRepository:
    """Wraps a summary repository and commits after each write."""

    def __init__(self, inner: ConversationSummaryRepository, sql: SqlSession) -> None:
        self._inner = inner
        self._sql = sql

    def get_latest(
        self,
        session_id: UUID,
        *,
        organization_id: UUID | None = None,
    ) -> ConversationSummary | None:
        return self._inner.get_latest(session_id, organization_id=organization_id)

    def upsert(self, summary: ConversationSummary) -> ConversationSummary:
        result = self._inner.upsert(summary)
        self._sql.commit()
        return result


def load_session_bundle(
    sql: SqlSession,
    session_id: UUID,
) -> tuple[SessionContract, AgentVersion]:
    session_repo = PostgresSessionRepository(SqlSessionRepository(sql))
    session = session_repo.get_session(session_id)
    if session is None:
        msg = f"session not found: {session_id}"
        raise LookupError(msg)

    version_row = AgentVersionRepository(sql).get(session.agent_version_id)
    if version_row is None:
        msg = f"agent version not found: {session.agent_version_id}"
        raise LookupError(msg)
    if version_row.id != session.agent_version_id:
        msg = "session agent_version_id mismatch"
        raise LookupError(msg)

    agent_version = version_to_contract(version_row)
    logger.info(
        "session_loaded",
        extra={
            "session_id": str(session.id),
            "agent_id": str(session.agent_id),
            "agent_version_id": str(session.agent_version_id),
            "config_hash": session.config_hash,
        },
    )
    return session, agent_version


def runtime_context_from_session(session: SessionContract) -> RuntimeContext:
    if session.config_hash is None:
        msg = f"session {session.id} missing config_hash"
        raise ValueError(msg)
    return RuntimeContext(
        session_id=session.id,
        organization_id=session.organization_id,
        project_id=session.project_id,
        agent_id=session.agent_id,
        agent_version_id=session.agent_version_id,
        config_hash=session.config_hash,
        deployment_id=session.deployment_id,
        channel=session.channel,
    )


def _llm_max_input_tokens(params: Mapping[str, JsonValue]) -> int | None:
    if "max_input_tokens" not in params:
        return None
    val = params["max_input_tokens"]
    if isinstance(val, bool) or not isinstance(val, int):
        msg = f"max_input_tokens must be an integer >= 1, got {type(val).__name__}: {val!r}"
        raise ValueError(msg)
    if val < 1:
        msg = f"max_input_tokens must be >= 1, got {val}"
        raise ValueError(msg)
    return val


def runtime_configs_from_version(
    version: AgentVersion,
) -> tuple[
    LLMRuntimeConfig,
    STTRuntimeConfig,
    TTSRuntimeConfig,
]:
    llm_key = normalize_llm_provider_key(version.llm.provider_key)
    return (
        LLMRuntimeConfig(
            provider_key=llm_key,
            model=version.llm.model,
            system_instructions=version.compiled_system_prompt(),
            params=dict(version.llm.params),
            max_input_tokens=_llm_max_input_tokens(version.llm.params),
        ),
        STTRuntimeConfig(
            provider_key=version.stt.provider_key,
            model=version.stt.model,
            language=version.locale,
            params=dict(version.stt.params),
        ),
        TTSRuntimeConfig(
            provider_key=version.tts.provider_key,
            voice_ref=version.tts.voice_ref,
            params=dict(version.tts.params),
        ),
    )


def create_providers_from_version(
    version: AgentVersion,
    *,
    llm_provider: LLMProvider | None = None,
    stt_provider: STTProvider | None = None,
    tts_provider: TTSProvider | None = None,
) -> tuple[LLMProvider, STTProvider, TTSProvider]:
    llm_config, stt_config, tts_config = runtime_configs_from_version(version)
    resolved_llm = llm_provider or create_llm_provider(
        llm_config.provider_key,
        model=llm_config.model,
    )
    resolved_stt = stt_provider or create_stt_provider(
        stt_config.provider_key,
        model=stt_config.model,
    )
    resolved_tts = tts_provider or create_tts_provider(
        tts_config.provider_key,
        voice_ref=tts_config.voice_ref,
    )
    logger.info(
        "providers_configured",
        extra={
            "agent_version_id": str(version.id),
            "llm_provider_key": llm_config.provider_key,
            "stt_provider_key": stt_config.provider_key,
            "tts_provider_key": tts_config.provider_key,
        },
    )
    return resolved_llm, resolved_stt, resolved_tts


def build_voice_worker(
    *,
    session: SessionContract,
    agent_version: AgentVersion,
    session_repository: SessionRepository,
    conversation_repository: ConversationRepository,
    summary_repository: ConversationSummaryRepository | None = None,
    transport: MediaTransport | None = None,
    llm_provider: LLMProvider | None = None,
    stt_provider: STTProvider | None = None,
    tts_provider: TTSProvider | None = None,
) -> VoiceWorkerComponents:
    if session.agent_version_id != agent_version.id:
        msg = "session is not pinned to the supplied agent version"
        raise ValueError(msg)

    context = runtime_context_from_session(session)
    llm_config, stt_config, tts_config = runtime_configs_from_version(agent_version)
    resolved_llm, resolved_stt, resolved_tts = create_providers_from_version(
        agent_version,
        llm_provider=llm_provider,
        stt_provider=stt_provider,
        tts_provider=tts_provider,
    )

    runtime = AgentRuntime(
        context,
        llm_provider=resolved_llm,
        llm_config=llm_config,
        stt_provider=resolved_stt,
        stt_config=stt_config,
        tts_provider=resolved_tts,
        tts_config=tts_config,
        session_repository=session_repository,
        conversation_repository=conversation_repository,
        summary_repository=summary_repository,
    )

    resolved_transport = transport or LiveKitMediaTransport()
    tts_resolver: TTSOutputAudioResolver | None = None
    if hasattr(resolved_tts, "resolve_output_audio"):
        tts_resolver = cast(TTSOutputAudioResolver, resolved_tts)

    bridge = RuntimeMediaBridge(
        runtime=runtime,
        transport=resolved_transport,
        tts_output_resolver=tts_resolver,
    )
    logger.info(
        "voice_worker_built",
        extra={
            "session_id": str(session.id),
            "agent_version_id": str(agent_version.id),
        },
    )
    return VoiceWorkerComponents(
        bridge=bridge,
        runtime=runtime,
        session=session,
        agent_version=agent_version,
    )


def build_voice_worker_from_db(
    sql: SqlSession,
    session_id: UUID,
    *,
    transport: MediaTransport | None = None,
    llm_provider: LLMProvider | None = None,
    stt_provider: STTProvider | None = None,
    tts_provider: TTSProvider | None = None,
) -> VoiceWorkerComponents:
    session, agent_version = load_session_bundle(sql, session_id)
    session_repo = cast(
        SessionRepository,
        _CommittingSessionRepository(
            PostgresSessionRepository(SqlSessionRepository(sql)),
            sql,
        ),
    )
    conversation_repo = cast(
        ConversationRepository,
        _CommittingConversationRepository(
            PostgresConversationRepository(SqlConversationRepository(sql)),
            sql,
        ),
    )
    summary_repo = cast(
        ConversationSummaryRepository,
        _CommittingConversationSummaryRepository(
            PostgresConversationSummaryRepository(SqlSummaryRepository(sql)),
            sql,
        ),
    )
    return build_voice_worker(
        session=session,
        agent_version=agent_version,
        session_repository=session_repo,
        conversation_repository=conversation_repo,
        summary_repository=summary_repo,
        transport=transport,
        llm_provider=llm_provider,
        stt_provider=stt_provider,
        tts_provider=tts_provider,
    )
