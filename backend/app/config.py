"""Runtime settings, read from environment variables."""
import os
import secrets

# Signs download tokens. Set it in production so tokens survive restarts and
# work across several workers; a random one is used otherwise.
SECRET_KEY = os.environ.get("SAVELOOP_SECRET_KEY") or secrets.token_urlsafe(32)

# How long a download link stays valid, in seconds.
TOKEN_TTL = int(os.environ.get("SAVELOOP_TOKEN_TTL", "900"))

# yt-dlp metadata lookup timeout, in seconds.
EXTRACT_TIMEOUT = float(os.environ.get("SAVELOOP_EXTRACT_TIMEOUT", "20"))

# Requests allowed per IP per minute, for extract and download separately.
EXTRACT_PER_MINUTE = int(os.environ.get("SAVELOOP_EXTRACT_PER_MINUTE", "10"))
DOWNLOAD_PER_MINUTE = int(os.environ.get("SAVELOOP_DOWNLOAD_PER_MINUTE", "30"))

# GIF conversion limits keep files small and CPU bounded.
GIF_MAX_SECONDS = float(os.environ.get("SAVELOOP_GIF_MAX_SECONDS", "15"))
GIF_WIDTH = int(os.environ.get("SAVELOOP_GIF_WIDTH", "480"))
GIF_FPS = int(os.environ.get("SAVELOOP_GIF_FPS", "12"))

# Set to "1" when running behind a reverse proxy that sets X-Forwarded-For.
TRUST_PROXY = os.environ.get("SAVELOOP_TRUST_PROXY", "0") == "1"

# Optional Netscape cookies file passed to yt-dlp (some Instagram/Facebook
# posts need it). Leave unset to extract anonymously.
COOKIES_FILE = os.environ.get("SAVELOOP_COOKIES_FILE") or None

FRONTEND_DIR = os.environ.get(
    "SAVELOOP_FRONTEND_DIR",
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend"),
)
