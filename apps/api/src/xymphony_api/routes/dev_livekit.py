from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from xymphony_api.config import Settings, get_settings
from xymphony_api.errors import AppError
from xymphony_api.schemas import LiveKitTokenResponse
from xymphony_realtime import LiveKitCredentials, mint_participant_token

router = APIRouter(prefix="/v1/dev", tags=["dev"])


def _require_development(settings: Settings) -> None:
    if settings.xymphony_env != "development":
        raise AppError(
            code="not_found",
            message="Not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )


def _livekit_credentials(settings: Settings) -> LiveKitCredentials:
    if not settings.livekit_configured:
        raise AppError(
            code="livekit_not_configured",
            message="LiveKit is not configured on the server",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return LiveKitCredentials(
        url=settings.livekit_url,  # type: ignore[arg-type]
        api_key=settings.livekit_api_key,  # type: ignore[arg-type]
        api_secret=settings.livekit_api_secret,  # type: ignore[arg-type]
    )


@router.post("/livekit/token", response_model=LiveKitTokenResponse)
async def mint_livekit_token(
    room: str = Query(..., min_length=1),
    identity: str = Query(..., min_length=1),
    settings: Settings = Depends(get_settings),
) -> LiveKitTokenResponse:
    """Development-only: mint a LiveKit participant token. Never returns API secrets."""
    _require_development(settings)
    credentials = _livekit_credentials(settings)
    participant = mint_participant_token(
        credentials,
        room_name=room,
        identity=identity,
    )
    return LiveKitTokenResponse(
        url=participant.url,
        room_name=participant.room_name,
        identity=participant.identity,
        token=participant.token,
    )
