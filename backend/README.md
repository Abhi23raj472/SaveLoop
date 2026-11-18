# SaveLoop backend

A FastAPI service that reads public post metadata with yt-dlp and streams files to the browser, converting with FFmpeg where needed. It serves the frontend too. Nothing is written to disk and no IPs or URLs are logged.

## Run locally

Needs Python 3.11+ and `ffmpeg` on your PATH.

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --no-access-log
```

Open http://localhost:8000. Run the tests with `pytest`.

With Docker, from the repo root:

```bash
docker build -t saveloop .
docker run -p 8000:8000 -e SAVELOOP_SECRET_KEY=change-me saveloop
```

## Endpoints

| Method | Path | What it does |
|---|---|---|
| POST | `/api/extract` | Takes `{"url": "..."}` and returns metadata plus download links (format in `frontend/README.md`). |
| GET | `/api/download/{token}` | Streams one file. Tokens are signed and expire after 15 minutes. |
| GET | `/healthz` | Health check. |

The download modes are:
- **MP4:** a progressive file is proxied as-is. Split video and audio are muxed by FFmpeg without re-encoding.
- **GIF:** the lowest quality video is converted by FFmpeg (first 15 s, 480 px wide, 12 fps).
- **WEBP / PNG:** the best thumbnail or image is converted by FFmpeg.

## Security

- **Allowed links:** only links on instagram.com, facebook.com, fb.watch, x.com and twitter.com (and their subdomains) are accepted. Bare IPs, other ports, credentials in the URL and other schemes are rejected.
- **Allowed media hosts:** the server only fetches media from the platforms' CDNs (cdninstagram.com, fbcdn.net, twimg.com and the like), and checks redirects against the same list. HLS/DASH manifests are skipped.
- **Signed tokens:** download links are HMAC-signed, so clients can't make the server fetch arbitrary URLs. Cookies never go into tokens.
- **Rate limits:** each IP gets 10 extracts and 30 downloads per minute. Counts are held in memory only.
- **Limited conversions:** at most 4 FFmpeg jobs run at once.
- **Headers:** responses send a strict CSP, `X-Frame-Options: DENY`, `nosniff` and `no-referrer`.

## Settings (environment variables)

| Variable | Default | Notes |
|---|---|---|
| `SAVELOOP_SECRET_KEY` | random per start | **Set this in production**, otherwise links break on restart or across workers. |
| `SAVELOOP_TOKEN_TTL` | `900` | Download link lifetime in seconds. |
| `SAVELOOP_EXTRACT_TIMEOUT` | `20` | yt-dlp timeout in seconds. |
| `SAVELOOP_EXTRACT_PER_MINUTE` / `SAVELOOP_DOWNLOAD_PER_MINUTE` | `10` / `30` | Rate limits per IP. |
| `SAVELOOP_GIF_MAX_SECONDS` / `SAVELOOP_GIF_WIDTH` / `SAVELOOP_GIF_FPS` | `15` / `480` / `12` | GIF limits. |
| `SAVELOOP_TRUST_PROXY` | `0` | Set to `1` behind a reverse proxy so rate limits use `X-Forwarded-For`. |
| `SAVELOOP_COOKIES_FILE` | unset | Optional cookies file for yt-dlp. Instagram and Facebook often block anonymous requests from server IPs. |

## Known limits

- Instagram and Facebook change often and may rate-limit or require login from datacenter IPs. Keep yt-dlp up to date (`pip install -U yt-dlp`), and expect to need a cookies file for reliable Instagram results.
- Rate limits live in memory, so with several workers or servers each one counts separately. Use a shared store such as Redis if you scale out.
