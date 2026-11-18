"""URL validation and SSRF protection.

Only public post links on known platforms are accepted, and the server only
ever fetches media from those platforms' CDNs.
"""
import ipaddress
from urllib.parse import urlsplit, urlunsplit

from . import errors

MAX_URL_LENGTH = 2048

# Hosts a submitted post link may point at (subdomains included).
PLATFORM_HOSTS = {
    "instagram": ("instagram.com", "instagr.am"),
    "facebook": ("facebook.com", "fb.watch", "fb.com"),
    "x": ("x.com", "twitter.com"),
}

# Hosts the server may fetch media bytes from (subdomains included).
MEDIA_HOSTS = (
    "cdninstagram.com",
    "instagram.com",
    "fbcdn.net",
    "facebook.com",
    "twimg.com",
    "x.com",
    "twitter.com",
)


def _host_matches(host: str, suffixes) -> bool:
    return any(host == s or host.endswith("." + s) for s in suffixes)


def _clean_host(parts) -> str:
    host = (parts.hostname or "").rstrip(".").lower()
    if not host:
        raise errors.invalid_url()
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return host
    # A bare IP address is never a valid platform or CDN host.
    raise errors.unsupported_platform()


def validate_post_url(raw: str) -> tuple[str, str]:
    """Return (normalized_url, platform) or raise ApiError."""
    if not isinstance(raw, str):
        raise errors.invalid_url()
    value = raw.strip()
    if not value or len(value) > MAX_URL_LENGTH or any(c.isspace() for c in value):
        raise errors.invalid_url()
    if "://" not in value:
        value = "https://" + value

    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        raise errors.invalid_url()

    if parts.scheme not in ("http", "https"):
        raise errors.invalid_url()
    if parts.username or parts.password:
        raise errors.invalid_url()
    if port not in (None, 80, 443):
        raise errors.invalid_url()

    host = _clean_host(parts)
    for platform, suffixes in PLATFORM_HOSTS.items():
        if _host_matches(host, suffixes):
            normalized = urlunsplit(("https", host, parts.path or "/", parts.query, ""))
            return normalized, platform
    raise errors.unsupported_platform()


def is_allowed_media_url(url: str) -> bool:
    """True when the server may fetch this media URL."""
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return False
    if parts.scheme != "https" or parts.username or parts.password:
        return False
    if port not in (None, 443):
        return False
    try:
        host = _clean_host(parts)
    except errors.ApiError:
        return False
    return _host_matches(host, MEDIA_HOSTS)
