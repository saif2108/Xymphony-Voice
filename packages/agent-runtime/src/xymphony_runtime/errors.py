"""Runtime-specific errors."""

from __future__ import annotations


class RuntimeError(Exception):
    """Base runtime error."""


class InvalidRuntimeInputError(RuntimeError):
    """Input event is malformed or unsupported in the current state."""


class InvalidStateTransitionError(RuntimeError):
    """Turn or runtime state transition is not allowed."""


class RuntimeNotRunningError(RuntimeError):
    """Operation requires a started runtime."""


class StaleTurnEventError(RuntimeError):
    """Event targets a cancelled turn and must not mutate state."""


class ContextBudgetExceededError(RuntimeError):
    """System instructions or current user input exceed the context budget."""
