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
