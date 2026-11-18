# SaveLoop

**Save the posts worth looping.** SaveLoop is a fast, ad-free web app for downloading public videos, GIFs and stickers from Instagram, Facebook and X. There's no sign-up, no watermark, and nothing is stored.

**Live:** https://saveloop-bzp8.onrender.com

## Features

- Paste a link from Instagram, Facebook or X and get your download options in a few seconds.
- **Video** as MP4 in the best available quality (1080p, 720p, 480p).
- **GIF** loops, including X's GIF posts, as real `.gif` files.
- **Stickers and stills** as WEBP or PNG.
- Works on phone and desktop. There's a one-tap Paste button.
- **Private by design:** no accounts, no database, no saved media, and no logging of IPs or links.

## How it works

1. The browser sends the post link to `POST /api/extract`.
2. The backend checks the link, reads the post's public metadata with [yt-dlp](https://github.com/yt-dlp/yt-dlp), and returns the formats as signed links that expire after 15 minutes.
3. When you click download, the server streams the file straight from the platform's CDN to your browser. FFmpeg converts it on the fly when needed (merging video with audio, or making a GIF, WEBP or PNG). Nothing is written to disk.

## Tech stack

| Part | Tools |
|---|---|
| Frontend | HTML5, Tailwind CSS 3, vanilla JavaScript, Plus Jakarta Sans |
| Backend | Python 3.11+, FastAPI, Uvicorn, yt-dlp, httpx, FFmpeg |
| Hosting | Docker on Render (free plan), set up by `render.yaml` |

## Project structure

```
SaveLoop/
├── frontend/          Single-page site (index.html, static/css, static/js)
├── backend/
│   ├── app/           FastAPI app: API, security, tokens, extraction, downloads
│   └── tests/         pytest suite
├── Dockerfile         Production image (Python 3.11 + FFmpeg)
├── render.yaml        Render Blueprint
└── .env.example       Example settings (copy to .env, never commit .env)
```

## Run locally

You need **Python 3.11+**, **Git** and **FFmpeg**.

**Windows (PowerShell)**

```powershell
winget install Gyan.FFmpeg       # then close and reopen PowerShell
cd $HOME
git clone https://github.com/Abhi23raj472/SaveLoop.git
cd SaveLoop\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --no-access-log
```

**macOS / Linux**

```bash
git clone https://github.com/Abhi23raj472/SaveLoop.git
cd SaveLoop/backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --no-access-log
```

Open http://localhost:8000. To preview the UI with sample data and no real downloads, open http://localhost:8000/?demo.

Run the tests with `pytest` from the `backend` folder.

**With Docker** (optional), from the repo root:

```bash
docker build -t saveloop .
docker run -p 8000:8000 --env-file .env saveloop
```

### Editing the styles

The built CSS (`frontend/static/css/styles.css`) is committed, so you only need Node.js if you change Tailwind classes:

```bash
cd frontend
npm install
npm run build
```

## Configuration

All settings are environment variables. Copy `.env.example` to `.env` for local use. The main ones:

| Variable | What it does |
|---|---|
| `SAVELOOP_SECRET_KEY` | Signs download links. Use a long random value in production. Render generates one for you. |
| `SAVELOOP_TRUST_PROXY` | Set to `1` behind a proxy such as Render, so rate limits see the real visitor IP. |
| `SAVELOOP_COOKIES_FILE` | Optional path to a cookies file for yt-dlp, for when Instagram blocks the server. |

The full list, the API reference and the security details are in [`backend/README.md`](backend/README.md). The response format and colors are in [`frontend/README.md`](frontend/README.md).

## Deploy on Render (free)

1. Sign in at [render.com](https://render.com) with GitHub.
2. Choose **New → Blueprint**, pick this repo, and click **Deploy Blueprint**. Render reads `render.yaml`, builds the Dockerfile, generates `SAVELOOP_SECRET_KEY`, and gives you a `https://saveloop-xxxx.onrender.com` address.
3. Every merge to `main` redeploys automatically.

The free plan sleeps after 15 minutes without visitors, so the first visit after a break takes about a minute.

## Security

- Only Instagram, Facebook and X links are accepted, and media is fetched only from their CDNs. This blocks SSRF.
- Download links are HMAC-signed and expire, so nobody can make the server fetch other URLs.
- Each IP gets 10 extracts and 30 downloads per minute.
- Strict security headers (CSP, `X-Frame-Options`, `nosniff`, `no-referrer`).
- No IP or URL logging. Access logs are turned off.

Secrets never go in the repo: `.env` and cookie files are git-ignored, and production secrets live in Render's environment settings.

## Roadmap

- GIF optimizer (smaller files, custom length)
- MP3 audio extraction
- PWA share target, so you can share a post from your phone straight to SaveLoop

## Disclaimer

SaveLoop is for saving public content for personal archiving. Respect creators' rights and each platform's terms. SaveLoop isn't affiliated with Instagram, Facebook, Meta or X.
