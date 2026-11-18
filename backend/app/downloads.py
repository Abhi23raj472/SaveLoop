"""Stream files to the client. Nothing is written to disk."""
import asyncio
from urllib.parse import urljoin

import httpx
from fastapi.responses import JSONResponse, StreamingResponse

from . import config
from .security import is_allowed_media_url

CHUNK = 64 * 1024
MAX_REDIRECTS = 3
# Caps concurrent ffmpeg jobs so conversions can't exhaust the CPU.
_ffmpeg_slots = asyncio.Semaphore(4)


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
    except httpx.HTTPError:
        await client.aclose()
        return _error(502, "extraction_failed", "Couldn't fetch the media. Please try again.")

    if resp.status_code != 200:
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
    await _ffmpeg_slots.acquire()
    try:
        proc = await asyncio.create_subprocess_exec(
            *build_ffmpeg_cmd(payload),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            stdin=asyncio.subprocess.DEVNULL,
        )
    except Exception:  # noqa: BLE001
        _ffmpeg_slots.release()
        return _error(500, "extraction_failed", "Conversion isn't available right now.")

    async def cleanup():
        if proc.returncode is None:
            proc.kill()
        await proc.wait()
        _ffmpeg_slots.release()

    # Wait for the first bytes so a failed conversion returns a clean error.
    try:
        first = await asyncio.wait_for(proc.stdout.read(CHUNK), timeout=60)
    except asyncio.TimeoutError:
        first = b""
    if not first:
        await cleanup()
        return _error(502, "extraction_failed", "We couldn't convert this file. Please try again.")

    async def body():
        try:
            yield first
            while chunk := await proc.stdout.read(CHUNK):
                yield chunk
        finally:
            await cleanup()

    headers = {"Content-Disposition": _disposition(payload.get("n", "download"), inline),
               "Cache-Control": "no-store"}
    return StreamingResponse(body(), media_type=payload.get("t") or "application/octet-stream",
                             headers=headers)
