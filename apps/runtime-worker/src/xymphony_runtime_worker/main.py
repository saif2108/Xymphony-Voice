"""Minimal runtime worker entrypoint — full voice agent via RuntimeMediaBridge."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from uuid import UUID

from xymphony_api.config import Settings
from xymphony_api.db import get_session_factory
from xymphony_contracts.media_transport import MediaTransportConfig
from xymphony_realtime import LiveKitCredentials, LiveKitMediaTransport, mint_participant_token
from xymphony_runtime import RuntimeWorkerSession
from xymphony_runtime_worker.bootstrap import build_voice_worker_from_db

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Xymphony realtime voice worker")
    parser.add_argument("--room", default=os.getenv("LIVEKIT_ROOM"))
    parser.add_argument(
        "--identity",
        default=os.getenv("LIVEKIT_WORKER_IDENTITY", "xymphony-worker"),
    )
    parser.add_argument("--session-id", default=os.getenv("XYMPHONY_SESSION_ID"))
    return parser


def load_credentials() -> LiveKitCredentials:
    url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    missing = [
        name
        for name, value in [
            ("LIVEKIT_URL", url),
            ("LIVEKIT_API_KEY", api_key),
            ("LIVEKIT_API_SECRET", api_secret),
        ]
        if not value
    ]
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")
    assert url is not None and api_key is not None and api_secret is not None
    return LiveKitCredentials(url=url, api_key=api_key, api_secret=api_secret)


def build_transport_config(*, room: str, identity: str) -> MediaTransportConfig:
    credentials = load_credentials()
    participant = mint_participant_token(
        credentials,
        room_name=room,
        identity=identity,
        name=identity,
    )
    return MediaTransportConfig(
        url=participant.url,
        room_name=participant.room_name,
        participant_identity=participant.identity,
        token=participant.token,
    )


def parse_session_id(raw: str | None) -> UUID:
    if not raw:
        raise SystemExit("XYMPHONY_SESSION_ID (or --session-id) is required")
    try:
        return UUID(raw)
    except ValueError as exc:
        raise SystemExit(f"Invalid session id: {raw}") from exc


async def run_worker(*, room: str | None, identity: str, session_id: UUID) -> None:
    settings = Settings()
    factory = get_session_factory(settings)
    sql = factory()
    try:
        transport = LiveKitMediaTransport()
        components = build_voice_worker_from_db(sql, session_id, transport=transport)
        resolved_room = room or components.session.livekit_room or "xymphony-dev"
        config = build_transport_config(room=resolved_room, identity=identity)
        worker = RuntimeWorkerSession(components.bridge)
        logger.info(
            "worker_starting",
            extra={
                "session_id": str(session_id),
                "room": resolved_room,
                "identity": identity,
                "agent_version_id": str(components.agent_version.id),
            },
        )
        await worker.run(config)
        sql.commit()
    except Exception:
        sql.rollback()
        raise
    finally:
        sql.close()
    logger.info(
        "worker_stopped",
        extra={"session_id": str(session_id)},
    )


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    args = build_parser().parse_args()
    session_id = parse_session_id(args.session_id)
    asyncio.run(run_worker(room=args.room, identity=args.identity, session_id=session_id))


if __name__ == "__main__":
    main()
