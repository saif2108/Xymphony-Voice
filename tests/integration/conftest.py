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
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from xymphony_api.config import Settings, get_settings
from xymphony_api.db import reset_engine
from xymphony_api.main import create_app
from xymphony_api.models import OrganizationRow, ProjectRow

ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = ROOT / "apps" / "api" / "alembic.ini"

ADMIN_URL = os.environ.get(
    "XYMPHONY_ADMIN_DATABASE_URL",
    "postgresql+psycopg://xymphony:xymphony@localhost:5432/postgres",
)
TEST_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://xymphony:xymphony@localhost:5432/xymphony_test",
)


def _ensure_test_database() -> None:
    last_error: Exception | None = None
    for _ in range(30):
        try:
            engine = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
            with engine.connect() as conn:
                exists = conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = 'xymphony_test'")
                ).scalar()
                if not exists:
                    conn.execute(text("CREATE DATABASE xymphony_test"))
            engine.dispose()
            return
        except Exception as exc:  # noqa: BLE001 — retry until Postgres is up
            last_error = exc
            time.sleep(1)
    raise RuntimeError(
        "PostgreSQL is not reachable. Start it with `docker compose up -d postgres`."
    ) from last_error


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
