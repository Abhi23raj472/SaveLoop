# SaveLoop frontend

A single-page site built with HTML, Tailwind CSS and vanilla JS.

## Run it

```bash
cd frontend
npm install
npm run build        # or: npm run dev (rebuilds CSS on change)
python3 -m http.server 8000
```

Open http://localhost:8000/?demo to try the full flow with sample data. In demo mode, a link containing "private" shows the private-post error.

`static/css/styles.css` is the built file and is committed, so the backend can serve the site without Node.

## API it expects

`POST /api/extract` with `{"url": "<post link>"}`.

Success (200):

```json
{
  "platform": "instagram | facebook | x",
  "kind": "Reel",
  "creator": "@handle",
  "duration": 24,
  "width": 1080,
  "height": 1920,
  "thumbnail": "https://…",
  "formats": [
    { "id": "v1080", "type": "video", "ext": "mp4", "quality": "1080p", "label": "MP4 1080p", "url": "/api/download/…" },
    { "id": "gif", "type": "gif", "ext": "gif", "label": "GIF loop", "url": "/api/download/…" },
    { "id": "png", "type": "image", "ext": "png", "label": "PNG sticker", "url": "/api/download/…" }
  ]
}
```

Error (4xx or 5xx): `{"error": {"code": "<code>", "message": "…"}}`. The codes the UI knows are `invalid_url`, `unsupported_platform`, `private`, `not_found`, `rate_limited` and `extraction_failed`.

## Colors

| Token | Hex | Use |
|---|---|---|
| ricotta | #FAF6F0 | Page background |
| forest | #1F4D36 | Buttons, CTAs, detected badge |
| forest-dark | #173A2A | Formats panel, hover |
| tomato | #E8472F | Headline accent, step lines |
| tomato-ink | #B8361F | Small red text (passes contrast) |
| ink | #15201A | Body text |
