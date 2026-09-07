"""RuntimeTurn lifecycle state machine tests."""

import pytest
from tests.helpers import ORG, SESSION_ID

from xymphony_runtime.errors import InvalidStateTransitionError
from xymphony_runtime.turn import RuntimeTurn, RuntimeTurnLifecycleState


def test_turn_lifecycle_happy_path() -> None:
    turn = RuntimeTurn.create(
        turn_id=__import__("uuid").uuid4(),
        session_id=SESSION_ID,
        organization_id=ORG,
        sequence=1,
    )
    assert turn.state == RuntimeTurnLifecycleState.CREATED
    turn.activate()
    assert turn.state == RuntimeTurnLifecycleState.ACTIVE
    turn.complete()
    assert turn.state == RuntimeTurnLifecycleState.COMPLETED
    assert turn.ended_at is not None


def test_turn_invalid_transition_from_terminal() -> None:
    turn = RuntimeTurn.create(
        turn_id=__import__("uuid").uuid4(),
        session_id=SESSION_ID,
        organization_id=ORG,
        sequence=1,
    )
    turn.activate()
    turn.cancel()
    with pytest.raises(InvalidStateTransitionError):
        turn.complete()
