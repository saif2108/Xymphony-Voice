from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from xymphony_api.config import get_settings
from xymphony_api.errors import register_exception_handlers
from xymphony_api.logging import configure_logging
from xymphony_api.routes.agents import router as agents_router
from xymphony_api.routes.dev_livekit import router as dev_livekit_router
from xymphony_api.routes.dev_pages import router as dev_pages_router
from xymphony_api.routes.documents import router as documents_router
from xymphony_api.routes.health import router as health_router
from xymphony_api.routes.knowledge_bases import router as knowledge_bases_router
from xymphony_api.routes.sessions import router as sessions_router
from xymphony_api.routes.tools import router as tools_router


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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(agents_router)
    app.include_router(sessions_router)
    app.include_router(dev_livekit_router)
    app.include_router(dev_pages_router)
    app.include_router(tools_router)
    app.include_router(knowledge_bases_router)
    app.include_router(documents_router)
    return app


app = create_app()
