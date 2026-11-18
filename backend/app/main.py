"""SaveLoop API and static frontend."""
import asyncio
import logging
import os

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, downloads, errors, extractor, tokens
from .ratelimit import RateLimiter
from .security import validate_post_url

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")

app = FastAPI(title="SaveLoop", docs_url=None, redoc_url=None, openapi_url=None)

extract_limiter = RateLimiter(config.EXTRACT_PER_MINUTE)
download_limiter = RateLimiter(config.DOWNLOAD_PER_MINUTE)

CSP = (
    "default-src 'self'; img-src 'self' data:; script-src 'self'; "
    "style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)


class ExtractRequest(BaseModel):
    url: str


def client_ip(request: Request) -> str:
    if config.TRUST_PROXY:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Content-Security-Policy", CSP)
    return response


@app.exception_handler(errors.ApiError)
async def api_error_handler(_: Request, exc: errors.ApiError):
    body = {"error": {"code": exc.code}}
    if exc.message:
        body["error"]["message"] = exc.message
    return JSONResponse(body, status_code=exc.status)


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, __: RequestValidationError):
    return JSONResponse({"error": {"code": "invalid_url"}}, status_code=400)


@app.post("/api/extract")
async def extract(body: ExtractRequest, request: Request):
    if not extract_limiter.allow(client_ip(request)):
        raise errors.rate_limited()
    url, platform = validate_post_url(body.url)
    try:
        info = await asyncio.wait_for(run_in_threadpool(extractor.fetch_info, url), config.EXTRACT_TIMEOUT)
    except asyncio.TimeoutError:
        raise errors.extraction_failed("This is taking too long. Please try again.") from None
    try:
        return extractor.build_result(info, platform)
    except errors.ApiError:
        raise
    except Exception:  # noqa: BLE001
        logging.getLogger("saveloop").exception("could not build result")
        raise errors.extraction_failed() from None


@app.get("/api/download/{token}")
async def download(token: str, request: Request, inline: int = 0):
    payload = tokens.verify(token)
    if payload is None:
        return JSONResponse(
            {"error": {"code": "link_expired", "message": "This download link has expired. Paste the post link again."}},
            status_code=410,
        )
    # Thumbnail previews don't count against the download limit.
    if payload.get("m") != "image" and not download_limiter.allow(client_ip(request)):
        raise errors.rate_limited()
    return await downloads.stream(payload, inline=bool(inline) or payload.get("m") == "image")


@app.get("/healthz")
async def healthz():
    return {"ok": True}


# ---------------------------------------------------------------- frontend
_frontend = os.path.abspath(config.FRONTEND_DIR)
_static = os.path.join(_frontend, "static")
if os.path.isdir(_static):
    app.mount("/static", StaticFiles(directory=_static), name="static")


@app.get("/", include_in_schema=False)
async def index():
    path = os.path.join(_frontend, "index.html")
    if not os.path.isfile(path):
        return JSONResponse({"error": {"code": "not_found"}}, status_code=404)
    return FileResponse(path, headers={"Cache-Control": "no-cache"})
