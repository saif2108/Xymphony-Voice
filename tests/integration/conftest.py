from __future__ import annotations

import os
import time
from collections.abc import Generator
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from xymphony_api.config import Settings, get_settings
from xymphony_api.db import reset_engine
from xymphony_api.main import create_app
from xymphony_api.models import OrganizationRow, ProjectRow

ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = ROOT / "apps" / "api" / "alembic.ini"

_settings = get_settings()
_app_url = make_url(_settings.database_url)

_POSTGRES_HOST = (
    os.environ.get("POSTGRES_HOST")
    or (_app_url.host if _app_url.host and _app_url.host != "localhost" else "127.0.0.1")
)
_POSTGRES_PORT = (
    os.environ.get("POSTGRES_PORT")
    or str(_app_url.port or 5432)
)
_POSTGRES_USER = (
    os.environ.get("POSTGRES_USER")
    or _app_url.username
    or "xymphony"
)
_POSTGRES_PASSWORD = (
    os.environ.get("POSTGRES_PASSWORD")
    or _app_url.password
    or "xymphony"
)

ADMIN_URL = os.environ.get(
    "XYMPHONY_ADMIN_DATABASE_URL",
    f"postgresql+psycopg://{_POSTGRES_USER}:{_POSTGRES_PASSWORD}@{_POSTGRES_HOST}:{_POSTGRES_PORT}/postgres",
)
TEST_URL = os.environ.get(
    "TEST_DATABASE_URL",
    f"postgresql+psycopg://{_POSTGRES_USER}:{_POSTGRES_PASSWORD}@{_POSTGRES_HOST}:{_POSTGRES_PORT}/xymphony_test",
)


def _ensure_test_database() -> None:
    last_error: Exception | None = None
    engine = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    try:
        for _ in range(30):
            try:
                with engine.connect() as conn:
                    exists = conn.execute(
                        text("SELECT 1 FROM pg_database WHERE datname = 'xymphony_test'")
                    ).scalar()
                    if not exists:
                        try:
                            conn.execute(text("CREATE DATABASE xymphony_test"))
                        except Exception as create_exc:
                            err_msg = str(create_exc).lower()
                            if (
                                "already exists" not in err_msg
                                and "duplicate_database" not in err_msg
                            ):
                                raise
                return
            except OperationalError as exc:
                last_error = exc
                time.sleep(1)
            except Exception as exc:
                url_str = engine.url.render_as_string(hide_password=True)
                raise RuntimeError(
                    f"PostgreSQL connection succeeded at {url_str}, "
                    f"but database initialization failed: {exc}"
                ) from exc
        url_str = engine.url.render_as_string(hide_password=True)
        raise RuntimeError(
            f"PostgreSQL is not reachable at {url_str} after 30 attempts. "
            "Start it with `docker compose up -d postgres`."
        ) from last_error
    finally:
        engine.dispose()


def _run_migrations(url: str) -> None:
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ROOT / "apps" / "api" / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def test_engine() -> Generator[Engine, None, None]:
    _ensure_test_database()
    _run_migrations(TEST_URL)
    engine = create_engine(TEST_URL, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    get_settings.cache_clear()
    reset_engine()
    return Settings(database_url=TEST_URL)


@pytest.fixture()
def db_session(test_engine: Engine) -> Generator[Session, None, None]:
    factory = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    session = factory()
    session.execute(
        text(
            "TRUNCATE conversation_messages, sessions, agent_versions, "
            "agents, projects, organizations CASCADE"
        )
    )
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def project_id(db_session: Session) -> str:
    org = OrganizationRow(id=uuid4(), name="Test Org", slug=f"org-{uuid4().hex[:8]}")
    db_session.add(org)
    db_session.flush()
    project = ProjectRow(
        id=uuid4(),
        organization_id=org.id,
        name="Test Project",
        slug=f"proj-{uuid4().hex[:8]}",
    )
    db_session.add(project)
    db_session.commit()
    return str(project.id)


@pytest.fixture()
def client(test_settings: Settings, db_session: Session) -> Generator[TestClient, None, None]:
    from xymphony_api.config import get_settings as settings_dep
    from xymphony_api.db import session_scope
    from xymphony_api.deps import get_db_session

    reset_engine()
    get_settings.cache_clear()
    os.environ["DATABASE_URL"] = TEST_URL

    def override_settings() -> Settings:
        return test_settings

    def override_db() -> Generator[Session, None, None]:
        # Use the app's real session_scope against the test DB (commits),
        # then tests rely on truncate at the start of db_session.
        yield from session_scope(test_settings)

    app = create_app()
    app.dependency_overrides[settings_dep] = override_settings
    app.dependency_overrides[get_db_session] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    reset_engine()


BINDING = {
    "llm": {"provider_key": "openai_compatible", "model": "gpt-4o-mini", "params": {}},
    "stt": {"provider_key": "assemblyai", "model": "universal-streaming", "params": {}},
    "tts": {"provider_key": "elevenlabs", "voice_ref": "voice_default", "params": {}},
}
