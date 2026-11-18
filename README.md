# SaveLoop

A fast, ad-free web app for saving public videos, GIFs and stickers from Instagram, Facebook and X. There's no sign-up and no watermark.

- `frontend/`: the single-page site (HTML, Tailwind CSS, vanilla JS)
- `backend/`: the FastAPI extraction service, which also serves the frontend

## Quick start

```bash
docker build -t saveloop .
docker run -p 8000:8000 -e SAVELOOP_SECRET_KEY=change-me saveloop
```

Then open http://localhost:8000. See `backend/README.md` and `frontend/README.md` for details.

## Deploy on Render (free)

1. Sign in at [render.com](https://render.com) with GitHub.
2. Choose **New → Blueprint**, pick this repo, and click **Apply**. Render reads `render.yaml`, builds the Dockerfile and gives you a `https://saveloop-xxxx.onrender.com` address.
3. Every merge to `main` redeploys automatically.

The free plan sleeps after 15 minutes without visitors, so the first visit after a break takes about a minute. If Instagram links fail with "private" on the server, add a cookies file. See `SAVELOOP_COOKIES_FILE` in `backend/README.md`.
