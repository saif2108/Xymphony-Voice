from collections.abc import Generator
from uuid import UUID

from fastapi import Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from xymphony_api.config import Settings, get_settings
from xymphony_api.db import session_scope
from xymphony_api.errors import AppError
from xymphony_api.services import AgentService, SessionService


def get_db_session(settings: Settings = Depends(get_settings)) -> Generator[Session, None, None]:
    yield from session_scope(settings)


def get_agent_service(session: Session = Depends(get_db_session)) -> AgentService:
    return AgentService(session)


def get_session_service(session: Session = Depends(get_db_session)) -> SessionService:
    return SessionService(session)


def pagination_limit(limit: int = Query(default=20, ge=1, le=100)) -> int:
    return limit


def optional_cursor(cursor: str | None = Query(default=None)) -> UUID | None:
    if cursor is None or cursor == "":
        return None
    try:
        return UUID(cursor)
    except ValueError as exc:
        raise AppError(
            code="validation_error",
            message="Invalid cursor",
            status_code=422,
        ) from exc


def check_database(session: Session) -> str:
    session.execute(text("SELECT 1"))
    return "connected"
