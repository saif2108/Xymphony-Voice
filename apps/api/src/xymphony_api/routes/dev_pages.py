from pathlib import Path

from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse

from xymphony_api.config import Settings, get_settings
from xymphony_api.errors import AppError
from xymphony_api.routes.dev_livekit import _require_development

router = APIRouter(tags=["dev"])

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static" / "dev"


@router.get("/dev/livekit")
async def dev_livekit_page(settings: Settings = Depends(get_settings)) -> FileResponse:
    """Development-only browser connectivity test for LiveKit media transport."""
    _require_development(settings)
    page = _STATIC_DIR / "livekit.html"
    if not page.is_file():
        raise AppError(
            code="not_found",
            message="Dev page missing",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return FileResponse(page, media_type="text/html")
