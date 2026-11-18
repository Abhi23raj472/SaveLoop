"""Stream files to the client. Nothing is written to disk."""
import asyncio
import logging
import re
import subprocess
import threading
from urllib.parse import urljoin

from fastapi.concurrency import run_in_threadpool

import httpx
from fastapi.responses import JSONResponse, StreamingResponse

from . import config
from .security import is_allowed_media_url

CHUNK = 64 * 1024
MAX_REDIRECTS = 3
# Caps concurrent ffmpeg jobs so conversions can't exhaust the CPU.
_ffmpeg_slots = threading.BoundedSemaphore(4)

# Logs why a download failed, never the URL or the client's IP.
log = logging.getLogger("saveloop")
_URL_RE = re.compile(r"https?://\S+")


def _scrub(text: str) -> str:
    return _URL_RE.sub("<url>", text)[-500:]


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


def _disposition(name: str, inline: bool) -> str:
    safe = "".join(c for c in name if c.isalnum() or c in "._-") or "download"
    return f'{"inline" if inline else "attachment"}; filename="{safe}"'


async def stream(payload: dict, inline: bool = False):
    urls = payload.get("u") or []
    if not urls or not all(isinstance(u, str) and is_allowed_media_url(u) for u in urls):
        return _error(400, "invalid_url", "This download link is not valid.")
    mode = payload.get("m")
    if mode in ("direct", "image"):
        return await _proxy(payload, inline)
    if mode in ("mux", "gif", "png", "webp"):
        return await _ffmpeg(payload, inline)
    return _error(400, "invalid_url", "This download link is not valid.")


# ---------------------------------------------------------------- direct

async def _proxy(payload: dict, inline: bool):
    client = httpx.AsyncClient(timeout=httpx.Timeout(15.0, read=30.0), follow_redirects=False)
    url = payload["u"][0]
    try:
        for _ in range(MAX_REDIRECTS + 1):
            req = client.build_request("GET", url, headers=payload.get("h") or {})
            resp = await client.send(req, stream=True)
            if resp.is_redirect:
                await resp.aclose()
                url = urljoin(url, resp.headers.get("location", ""))
                if not is_allowed_media_url(url):
                    await client.aclose()
                    return _error(502, "extraction_failed", "The media host redirected somewhere unexpected.")
                continue
            break
        else:
            await client.aclose()
            return _error(502, "extraction_failed", "Too many redirects.")
    except httpx.HTTPError as exc:
        await client.aclose()
        log.warning("media fetch failed: %s", type(exc).__name__)
        return _error(502, "extraction_failed", "Couldn't fetch the media. Please try again.")

    if resp.status_code != 200:
        log.warning("media host returned HTTP %s", resp.status_code)
        await resp.aclose()
        await client.aclose()
        code = "link_expired" if resp.status_code in (403, 410) else "extraction_failed"
        return _error(502, code, "The media link has expired. Paste the post link again.")

    async def body():
        try:
            async for chunk in resp.aiter_bytes(CHUNK):
                yield chunk
        finally:
            await resp.aclose()
            await client.aclose()

    headers = {"Content-Disposition": _disposition(payload.get("n", "download"), inline),
               "Cache-Control": "no-store"}
    if "content-length" in resp.headers:
        headers["Content-Length"] = resp.headers["content-length"]
    media_type = payload.get("t") or resp.headers.get("content-type", "application/octet-stream")
    return StreamingResponse(body(), media_type=media_type, headers=headers)


# ---------------------------------------------------------------- ffmpeg

def _input_args(url: str, headers: dict) -> list[str]:
    args = ["-protocol_whitelist", "https,tls,tcp"]
    if headers:
        args += ["-headers", "".join(f"{k}: {v}\r\n" for k, v in headers.items())]
    return args + ["-i", url]


def build_ffmpeg_cmd(payload: dict) -> list[str]:
    mode, urls, h = payload["m"], payload["u"], payload.get("h") or {}
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin"]
    if mode == "mux":
        for u in urls:
            cmd += _input_args(u, h)
        cmd += ["-map", "0:v:0"]
        if len(urls) > 1:
            cmd += ["-map", "1:a:0"]
        cmd += ["-c", "copy", "-movflags", "frag_keyframe+empty_moov", "-f", "mp4", "pipe:1"]
    elif mode == "gif":
        cmd += ["-t", str(config.GIF_MAX_SECONDS)] + _input_args(urls[0], h)
        vf = (f"fps={config.GIF_FPS},scale={config.GIF_WIDTH}:-1:flags=lanczos,"
              "split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer")
        cmd += ["-vf", vf, "-an", "-loop", "0", "-f", "gif", "pipe:1"]
    elif mode == "png":
        cmd += _input_args(urls[0], h) + ["-frames:v", "1", "-f", "image2pipe", "-c:v", "png", "pipe:1"]
    elif mode == "webp":
        cmd += _input_args(urls[0], h) + ["-frames:v", "1", "-f", "image2pipe", "-c:v", "libwebp",
                                          "-quality", "90", "pipe:1"]
    else:
        raise ValueError(mode)
    return cmd


async def _ffmpeg(payload: dict, inline: bool):
    # subprocess.Popen in a thread works on every event loop, including the
    # Windows selector loop where asyncio subprocesses are not supported.
    if not _ffmpeg_slots.acquire(blocking=False):
        return _error(503, "rate_limited", "The server is busy converting files. Please try again shortly.")
    try:
        proc = subprocess.Popen(
            build_ffmpeg_cmd(payload),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        _ffmpeg_slots.release()
        log.error("ffmpeg is not installed or not on PATH")
        return _error(500, "extraction_failed", "Conversion isn't available: FFmpeg is not installed on the server.")
    except Exception as exc:  # noqa: BLE001
        _ffmpeg_slots.release()
        log.error("could not start ffmpeg: %s", type(exc).__name__)
        return _error(500, "extraction_failed", "Conversion isn't available right now.")

    stderr_tail = []

    def drain_stderr():
        for line in proc.stderr:
            stderr_tail.append(line.decode(errors="replace"))
            del stderr_tail[:-20]

    threading.Thread(target=drain_stderr, daemon=True).start()

    released = False

    def cleanup():
        nonlocal released
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        if not released:
            released = True
            _ffmpeg_slots.release()

    try:
        first = await asyncio.wait_for(run_in_threadpool(proc.stdout.read1, CHUNK), timeout=60)
    except asyncio.TimeoutError:
        first = b""
    if not first:
        await run_in_threadpool(cleanup)
        log.warning("ffmpeg produced no output (exit %s): %s", proc.returncode, _scrub("".join(stderr_tail)))
        return _error(502, "extraction_failed", "We couldn't convert this file. Please try again.")

    async def body():
        try:
            yield first
            while chunk := await run_in_threadpool(proc.stdout.read1, CHUNK):
                yield chunk
        finally:
            await run_in_threadpool(cleanup)

    headers = {"Content-Disposition": _disposition(payload.get("n", "download"), inline),
               "Cache-Control": "no-store"}
    return StreamingResponse(body(), media_type=payload.get("t") or "application/octet-stream",
                             headers=headers)
