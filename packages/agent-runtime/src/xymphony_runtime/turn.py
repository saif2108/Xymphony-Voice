"""In-process turn lifecycle for AgentRuntime (maps to xymphony_contracts.Turn)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from xymphony_contracts import Turn
from xymphony_contracts.enums import TurnStatus
from xymphony_runtime.errors import InvalidStateTransitionError


class RuntimeTurnLifecycleState(StrEnum):
    CREATED = "created"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"

    def to_turn_status(self) -> TurnStatus:
        mapping = {
            RuntimeTurnLifecycleState.CREATED: TurnStatus.IN_PROGRESS,
            RuntimeTurnLifecycleState.ACTIVE: TurnStatus.IN_PROGRESS,
            RuntimeTurnLifecycleState.COMPLETED: TurnStatus.COMMITTED,
            RuntimeTurnLifecycleState.CANCELLED: TurnStatus.CANCELLED,
            RuntimeTurnLifecycleState.FAILED: TurnStatus.FAILED,
        }
        return mapping[self]

    @property
    def is_terminal(self) -> bool:
        return self in {
            RuntimeTurnLifecycleState.COMPLETED,
            RuntimeTurnLifecycleState.CANCELLED,
            RuntimeTurnLifecycleState.FAILED,
        }


_TERMINAL: frozenset[RuntimeTurnLifecycleState] = frozenset(
    state for state in RuntimeTurnLifecycleState if state.is_terminal
)

_ALLOWED: dict[RuntimeTurnLifecycleState, frozenset[RuntimeTurnLifecycleState]] = {
    RuntimeTurnLifecycleState.CREATED: frozenset({RuntimeTurnLifecycleState.ACTIVE}),
    RuntimeTurnLifecycleState.ACTIVE: frozenset(
        {
            RuntimeTurnLifecycleState.COMPLETED,
            RuntimeTurnLifecycleState.CANCELLED,
            RuntimeTurnLifecycleState.FAILED,
        }
    ),
}


@dataclass
class RuntimeTurn:
    id: UUID
    session_id: UUID
    organization_id: UUID
    sequence: int
    state: RuntimeTurnLifecycleState
    started_at: datetime
    ended_at: datetime | None = None
    interrupted: bool = False
    error_code: str | None = None

    @classmethod
    def create(
        cls,
        *,
        turn_id: UUID,
        session_id: UUID,
        organization_id: UUID,
        sequence: int,
        started_at: datetime | None = None,
    ) -> RuntimeTurn:
        return cls(
            id=turn_id,
            session_id=session_id,
            organization_id=organization_id,
            sequence=sequence,
            state=RuntimeTurnLifecycleState.CREATED,
            started_at=started_at or datetime.now(UTC),
        )

    def _transition(self, target: RuntimeTurnLifecycleState) -> None:
        if self.state in _TERMINAL:
            raise InvalidStateTransitionError(
                f"turn {self.id} cannot leave terminal state {self.state.value}"
            )
        allowed = _ALLOWED.get(self.state, frozenset())
        if target not in allowed:
            raise InvalidStateTransitionError(
                f"turn {self.id} cannot transition {self.state.value} -> {target.value}"
            )
        self.state = target

    def activate(self) -> None:
        self._transition(RuntimeTurnLifecycleState.ACTIVE)

    def complete(self) -> None:
        self._transition(RuntimeTurnLifecycleState.COMPLETED)
        self.ended_at = datetime.now(UTC)

    def cancel(self, *, interrupted: bool = True) -> None:
        self._transition(RuntimeTurnLifecycleState.CANCELLED)
        self.interrupted = interrupted
        self.ended_at = datetime.now(UTC)

    def fail(self, *, error_code: str) -> None:
        self._transition(RuntimeTurnLifecycleState.FAILED)
        self.error_code = error_code
        self.ended_at = datetime.now(UTC)

    def to_contract(self) -> Turn:
        return Turn(
            id=self.id,
            session_id=self.session_id,
            organization_id=self.organization_id,
            sequence=self.sequence,
            status=self.state.to_turn_status(),
            started_at=self.started_at,
            ended_at=self.ended_at,
            interrupted=self.interrupted,
        )
