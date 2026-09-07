"""Runtime observations surfaced from transport events and lifecycle transitions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from xymphony_contracts.media_transport import TransportErrorEvent, TransportParticipantEvent
from xymphony_runtime.lifecycle import RuntimeSessionLifecycleState


@dataclass(frozen=True)
class LifecycleTransition:
    state: RuntimeSessionLifecycleState
    at: datetime


RuntimeObservation = LifecycleTransition | TransportParticipantEvent | TransportErrorEvent


def lifecycle_transition(state: RuntimeSessionLifecycleState) -> LifecycleTransition:
    return LifecycleTransition(state=state, at=datetime.now(UTC))
