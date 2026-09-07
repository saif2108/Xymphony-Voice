from uuid import uuid4

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from xymphony_api.config import get_settings
from xymphony_api.errors import register_exception_handlers
from xymphony_api.logging import configure_logging
from xymphony_api.routes.agents import router as agents_router
from xymphony_api.routes.dev_livekit import router as dev_livekit_router
from xymphony_api.routes.dev_pages import router as dev_pages_router
from xymphony_api.routes.health import router as health_router


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title="Xymphony Voice API", version="0.1.0")
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(agents_router)
    app.include_router(dev_livekit_router)
    app.include_router(dev_pages_router)
    return app


app = create_app()
