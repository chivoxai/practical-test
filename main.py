"""FastAPI entry point — POST /prospect-discovery on port 4000."""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Deque, Dict

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from app.config import settings
from app.platforms import PLATFORM_REGISTRY
from app.platforms.google import SearchClient
from app.schemas import ProspectRequest, ProspectResponse
from app.services.llm_service import LLMError, LLMService
from app.services.prospect_service import NoSourcesError, ProspectService
from app.services.query_service import InvalidQueryError
from app.utils.http import create_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("prospect.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    http = create_client()
    app.state.http = http
    app.state.service = ProspectService(http=http, search=SearchClient(http), llm=LLMService(http))
    log.info("ready: LLM providers=%s, search backend=%s (configured=%s), youtube_api=%s",
             app.state.service.llm.providers(), settings.search_backend,
             app.state.service.search.configured, bool(settings.youtube_api_key))
    yield
    await http.aclose()


app = FastAPI(
    title="AI-Powered Multi-Platform Prospect Discovery API",
    version="1.0.0",
    description="Finds public prospect profiles across Google, LinkedIn, X, YouTube, Instagram, Facebook, "
                "Threads, plus published email / phone / WhatsApp contacts, from a natural-language query.",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])


def _error(status: int, query: str, message: str) -> JSONResponse:
    body = ProspectResponse(success=False, query=query, total_prospects=0, prospects=[], error=message).to_public()
    return JSONResponse(status_code=status, content=body)


# --------------------------------------------------------------------------- #
# Simple per-IP sliding-window rate limit (in-memory; use Redis behind a LB)
# --------------------------------------------------------------------------- #
_hits: Dict[str, Deque[float]] = defaultdict(deque)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.url.path.startswith("/prospect-discovery") and settings.rate_limit_per_minute > 0:
        ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0].strip()
        now = time.monotonic()
        q = _hits[ip]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= settings.rate_limit_per_minute:
            return _error(429, "", f"rate limit exceeded: {settings.rate_limit_per_minute} requests/minute")
        q.append(now)
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    query = ""
    try:
        body = await request.json()
        query = str(body.get("query", "")) if isinstance(body, dict) else ""
    except Exception:
        pass
    msgs = "; ".join(f"{'.'.join(str(x) for x in e['loc'][1:]) or 'body'}: {e['msg']}" for e in exc.errors())
    return _error(422, query, f"invalid request: {msgs}")


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    log.exception("unhandled error")
    return _error(500, "", "internal error while processing the request")


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.post("/prospect-discovery", response_model=ProspectResponse, response_model_exclude_none=True,
          summary="Discover public prospects from a natural-language query")
async def prospect_discovery(
    payload: ProspectRequest,
    request: Request,
    include_evidence: bool = Query(False, description="Add per-prospect match status, evidence and merge reasons"),
    debug: bool = Query(False, description="Add parsed query, generated searches, platform status, token usage"),
):
    service: ProspectService = request.app.state.service
    try:
        resp = await service.discover(payload.query, include_evidence=include_evidence, debug=debug)
    except InvalidQueryError as e:
        return _error(422, payload.query, f"invalid query: {e}")
    except NoSourcesError as e:
        return _error(503, payload.query, str(e))
    except LLMError as e:
        return _error(502, payload.query, f"LLM failure: {e}")
    return JSONResponse(content=resp.to_public())


@app.get("/health", summary="Liveness + which integrations are configured (no secrets)")
async def health(request: Request):
    service: ProspectService = request.app.state.service
    return {
        "status": "ok",
        "llm_providers": service.llm.providers(),
        "search_backend": settings.search_backend,
        "search_configured": service.search.configured,
        "youtube_api": bool(settings.youtube_api_key),
        "platforms": list(PLATFORM_REGISTRY.keys()),
    }


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse("/docs")


if __name__ == "__main__":  # python -m app.main
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.port)
