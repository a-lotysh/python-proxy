from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from proxy.api.dispatch import router
from proxy.api.middleware import RecordingMiddleware
from proxy.core.config import settings
from proxy.core.exceptions import register_exception_handlers
from proxy.core.http_client import UpstreamClient


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    httpx_client = httpx.AsyncClient(
        timeout=settings.upstream_timeout_s,
        headers={"Accept": "application/json"},
        follow_redirects=True,
    )
    app.state.upstream_client = UpstreamClient(httpx_client)
    try:
        yield
    finally:
        await httpx_client.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan)
    app.add_middleware(RecordingMiddleware)
    register_exception_handlers(app)
    app.include_router(router)

    return app


app = create_app()
