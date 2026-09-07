"""LiveKit access token minting. Uses livekit-api only — no rtc Room here."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from livekit import api


@dataclass(frozen=True)
class LiveKitCredentials:
    url: str
    api_key: str
    api_secret: str


@dataclass(frozen=True)
class LiveKitParticipantToken:
    url: str
    room_name: str
    identity: str
    token: str


def mint_participant_token(
    credentials: LiveKitCredentials,
    *,
    room_name: str,
    identity: str,
    name: str | None = None,
    ttl_seconds: int = 3600,
    can_publish: bool = True,
    can_subscribe: bool = True,
) -> LiveKitParticipantToken:
    grant = api.VideoGrants(
        room_join=True,
        room=room_name,
        can_publish=can_publish,
        can_subscribe=can_subscribe,
    )
    token = (
        api.AccessToken(credentials.api_key, credentials.api_secret)
        .with_identity(identity)
        .with_name(name or identity)
        .with_ttl(timedelta(seconds=ttl_seconds))
        .with_grants(grant)
        .to_jwt()
    )
    return LiveKitParticipantToken(
        url=credentials.url,
        room_name=room_name,
        identity=identity,
        token=token,
    )
