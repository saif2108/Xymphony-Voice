"""Runtime worker session lifecycle states (Step 4)."""

from __future__ import annotations

from enum import StrEnum

from xymphony_contracts.enums import SessionStatus


class RuntimeSessionLifecycleState(StrEnum):
    """In-process worker session lifecycle. Maps to SessionStatus where applicable."""

    INITIALIZING = "initializing"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"

    def to_session_status(self) -> SessionStatus | None:
        mapping: dict[RuntimeSessionLifecycleState, SessionStatus] = {
            RuntimeSessionLifecycleState.INITIALIZING: SessionStatus.INITIALIZING,
            RuntimeSessionLifecycleState.CONNECTED: SessionStatus.ACTIVE,
            RuntimeSessionLifecycleState.STOPPED: SessionStatus.TERMINATED,
            RuntimeSessionLifecycleState.FAILED: SessionStatus.FAILED,
        }
        return mapping.get(self)
