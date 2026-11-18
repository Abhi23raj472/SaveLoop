"""Turn a post URL into metadata plus signed download links, using yt-dlp.

Nothing is downloaded here: yt-dlp only reads metadata and direct media URLs.
"""
import logging
import re
import shutil

import yt_dlp

from . import config, errors, tokens
from .security import is_allowed_media_url

log = logging.getLogger("saveloop")
_URL_RE = re.compile(r"https?://\S+")

QUALITY_TARGETS = (1080, 720, 480)
SAFE_HEADERS = ("User-Agent", "Referer", "Origin")
KIND_LABELS = {"instagram": "Post", "facebook": "Video", "x": "Post"}


class _SilentLogger:
    """Keeps yt-dlp from printing URLs or other request details."""

    def debug(self, msg):
        pass

    info = warning = debug

    def error(self, msg):
        pass


def _ydl_opts() -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": 10,
        "logger": _SilentLogger(),
        "cachedir": False,
    }
    if config.COOKIES_FILE:
        opts["cookiefile"] = config.COOKIES_FILE
    return opts


def fetch_info(url: str) -> dict:
    """Run yt-dlp metadata extraction (blocking). Raises ApiError."""
    try:
        with yt_dlp.YoutubeDL(_ydl_opts()) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        err = map_ytdlp_error(str(exc))
        # Logged so the operator can see why; URLs are scrubbed.
        log.warning("yt-dlp failed (%s): %s", err.code, _URL_RE.sub("<url>", str(exc))[:400])
        raise err from None
    except Exception as exc:  # noqa: BLE001 - never leak internals to the client
        log.exception("yt-dlp crashed: %s", type(exc).__name__)
        raise errors.extraction_failed() from None
    if not info:
        raise errors.not_found()
    return info


def has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def map_ytdlp_error(message: str) -> errors.ApiError:
    m = message.lower()
    if "is not a video" in m or "no video could be found" in m:
        return errors.no_video("This post only has photos. SaveLoop can save videos and GIFs for now.")
    if "unsupported url" in m:
        return errors.unsupported_platform()
    if any(k in m for k in ("private", "login required", "log in", "requires authentication", "age-restricted")):
        return errors.private()
    if any(k in m for k in ("not found", "404", "does not exist", "unavailable", "removed", "deleted")):
        return errors.not_found()
    if "429" in m or "too many requests" in m:
        return errors.rate_limited("The platform is busy right now. Please try again in a minute.")
    return errors.extraction_failed()


# ---------------------------------------------------------------- helpers

def _first_entry(info: dict) -> dict:
    entries = info.get("entries")
    if entries:
        for entry in entries:
            if entry:
                return entry
    return info


def _headers(fmt_or_info: dict) -> dict:
    h = fmt_or_info.get("http_headers") or {}
    return {k: v for k, v in h.items() if k in SAFE_HEADERS and isinstance(v, str)}


def _short_side(f: dict) -> int:
    w, h = f.get("width") or 0, f.get("height") or 0
    if w and h:
        return min(w, h)
    return h or w or 0


def _is_direct(f: dict) -> bool:
    return (
        f.get("protocol") in ("https", "http")
        and isinstance(f.get("url"), str)
        and is_allowed_media_url(f["url"])
    )


def _has_video(f: dict) -> bool:
    return f.get("vcodec") not in (None, "none") or (f.get("vcodec") is None and bool(f.get("height")))


def _has_audio(f: dict) -> bool:
    return f.get("acodec") not in (None, "none")


def _slug(value: str, limit: int = 40) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", value or "").strip("-")[:limit] or "media"


def _pick_video_sources(formats: list[dict], can_mux: bool = True) -> list[dict]:
    """For each quality target, choose a progressive format or a video+audio pair."""
    direct = [f for f in formats if _is_direct(f)]
    progressive = [f for f in direct if _has_video(f) and _has_audio(f)]
    video_only = [f for f in direct if _has_video(f) and not _has_audio(f)]
    audio_only = [f for f in direct if _has_audio(f) and not _has_video(f)]
    best_audio = max(audio_only, key=lambda f: f.get("abr") or f.get("tbr") or 0, default=None)
    if not can_mux:
        # Without FFmpeg only ready-made files with sound can be offered.
        video_only, best_audio = ([] if progressive else video_only), None

    candidates = progressive + (video_only if best_audio else [])
    if not candidates:
        candidates = video_only  # silent clips (e.g. GIF-style posts)

    picks, seen = [], set()
    for target in QUALITY_TARGETS:
        fitting = [f for f in candidates if 0 < _short_side(f) <= target]
        if not fitting:
            continue
        # Prefer the tallest fit; on ties prefer a progressive file (no muxing).
        best = max(fitting, key=lambda f: (_short_side(f), _has_audio(f), f.get("tbr") or 0))
        side = _short_side(best)
        if side in seen:
            continue
        seen.add(side)
        picks.append({"fmt": best, "audio": None if _has_audio(best) else best_audio, "side": side})

    if not picks:
        # No size info at all: fall back to the single best direct format.
        fallback = max(progressive or video_only, key=lambda f: f.get("tbr") or 0, default=None)
        if fallback:
            picks.append({"fmt": fallback, "audio": None if _has_audio(fallback) else best_audio, "side": 0})
    return picks


def _best_thumbnail(info: dict) -> str | None:
    thumbs = [t for t in (info.get("thumbnails") or []) if isinstance(t.get("url"), str)]
    thumbs = [t for t in thumbs if is_allowed_media_url(t["url"])]
    if thumbs:
        best = max(thumbs, key=lambda t: ((t.get("width") or 0) * (t.get("height") or 0), t.get("preference") or 0))
        return best["url"]
    thumb = info.get("thumbnail")
    return thumb if isinstance(thumb, str) and is_allowed_media_url(thumb) else None


# ---------------------------------------------------------------- main

def build_result(info: dict, platform: str) -> dict:
    entry = _first_entry(info)
    formats = entry.get("formats") or ([entry] if entry.get("url") else [])
    base = f"saveloop-{platform}-{_slug(str(entry.get('id') or ''))}"
    out_formats = []

    ffmpeg = has_ffmpeg()
    picks = _pick_video_sources(formats, can_mux=ffmpeg)
    for p in picks:
        f, audio = p["fmt"], p["audio"]
        quality = f"{p['side']}p" if p["side"] else "Best"
        payload = {
            "m": "mux" if audio else "direct",
            "u": [f["url"]] + ([audio["url"]] if audio else []),
            "h": _headers(f) or _headers(entry),
            "n": f"{base}-{quality}.mp4",
            "t": "video/mp4",
        }
        out_formats.append({
            "id": f"v{p['side'] or 'best'}",
            "type": "video",
            "ext": "mp4",
            "quality": quality,
            "label": f"MP4 {quality}",
            "url": f"/api/download/{tokens.sign(payload)}",
        })

    if picks and ffmpeg:
        smallest = min(picks, key=lambda p: p["side"] or 10_000)["fmt"]
        payload = {"m": "gif", "u": [smallest["url"]], "h": _headers(smallest) or _headers(entry),
                   "n": f"{base}.gif", "t": "image/gif"}
        out_formats.append({"id": "gif", "type": "gif", "ext": "gif", "label": "GIF loop",
                            "url": f"/api/download/{tokens.sign(payload)}"})

    thumb = _best_thumbnail(entry)
    preview_url = None
    if thumb:
        h = _headers(entry)
        if ffmpeg:
            for ext, mime in (("webp", "image/webp"), ("png", "image/png")):
                payload = {"m": ext, "u": [thumb], "h": h, "n": f"{base}.{ext}", "t": mime}
                out_formats.append({"id": ext, "type": "image", "ext": ext, "label": f"{ext.upper()} image",
                                    "url": f"/api/download/{tokens.sign(payload)}"})
        else:
            payload = {"m": "direct", "u": [thumb], "h": h, "n": f"{base}.jpg", "t": "image/jpeg"}
            out_formats.append({"id": "jpg", "type": "image", "ext": "jpg", "label": "JPG image",
                                "url": f"/api/download/{tokens.sign(payload)}"})
        preview_url = f"/api/download/{tokens.sign({'m': 'image', 'u': [thumb], 'h': h, 'n': 'preview', 't': ''})}?inline=1"

    if not out_formats:
        raise errors.not_found("This post has no video or image we can save.")

    creator = entry.get("uploader_id") or entry.get("channel") or entry.get("uploader") or ""
    if creator and not creator.startswith("@") and " " not in creator:
        creator = "@" + creator
    width, height = entry.get("width"), entry.get("height")
    if not (width and height) and picks:
        width, height = picks[0]["fmt"].get("width"), picks[0]["fmt"].get("height")

    return {
        "platform": platform,
        "kind": KIND_LABELS.get(platform, "Post") if picks else "Image",
        "creator": creator or None,
        "title": (entry.get("title") or "")[:200] or None,
        "duration": entry.get("duration"),
        "width": width,
        "height": height,
        "thumbnail": preview_url,
        "formats": out_formats,
    }
