"""Minimal runtime worker entrypoint — joins LiveKit via MediaTransport."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from uuid import uuid4

from xymphony_contracts.media_transport import MediaTransportConfig
from xymphony_realtime import LiveKitCredentials, LiveKitMediaTransport, mint_participant_token
from xymphony_runtime import RuntimeWorkerSession

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Xymphony minimal realtime transport worker")
    parser.add_argument("--room", default=os.getenv("LIVEKIT_ROOM", "xymphony-dev"))
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


async def run_worker(*, room: str, identity: str, session_id: str) -> None:
    worker = RuntimeWorkerSession(session_id=session_id)
    transport = LiveKitMediaTransport()
    config = build_transport_config(room=room, identity=identity)
    logger.info(
        "worker_starting",
        extra={"session_id": session_id, "room": room, "identity": identity},
    )
    await worker.run(transport, config)
    logger.info(
        "worker_stopped",
        extra={"session_id": session_id, "lifecycle_state": worker.lifecycle_state.value},
    )


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    args = build_parser().parse_args()
    session_id = args.session_id or str(uuid4())
    asyncio.run(run_worker(room=args.room, identity=args.identity, session_id=session_id))


if __name__ == "__main__":
    main()
