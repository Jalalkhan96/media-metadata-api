# Media Metadata API

Metadata-only API for public media URLs (YouTube, TikTok, Reddit,
Pinterest, Vimeo, Dailymotion, X, Instagram and 1000+ more sites).

Give it a link → get back public metadata: title, duration, thumbnail,
channel/uploader, views, likes, upload date, description and the
quality/format list (labels only).

**This API does not download media and never returns direct media or
stream URLs.** It only reads the public metadata of a page, the same
information any visitor's browser already sees.

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/` | – | API info |
| GET | `/health` | – | Health check |
| GET | `/api/info?url=<url>` | `X-API-Key` | Metadata for one media URL |
| POST | `/api/info` | `X-API-Key` | Same, JSON body `{"url": "..."}` |
| GET | `/api/search?q=<query>&limit=5` | `X-API-Key` | YouTube search metadata |

Interactive docs: `/docs`

## Usage — curl

```bash
curl "https://YOUR-SERVICE.onrender.com/api/info?url=https://www.youtube.com/watch?v=VIDEO_ID" \
  -H "X-API-Key: YOUR_KEY"
```

## Usage — Node.js

```js
const BASE = "https://YOUR-SERVICE.onrender.com";
const KEY = process.env.METADATA_API_KEY;

async function getInfo(mediaUrl) {
  const res = await fetch(`${BASE}/api/info?url=${encodeURIComponent(mediaUrl)}`, {
    headers: { "X-API-Key": KEY },
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res.json(); // { title, duration_seconds, thumbnail, channel, view_count, source_url, formats: [...] }
}

async function searchYouTube(query, limit = 5) {
  const res = await fetch(`${BASE}/api/search?q=${encodeURIComponent(query)}&limit=${limit}`, {
    headers: { "X-API-Key": KEY },
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res.json(); // { query, count, results: [{ id, title, url, duration_seconds, channel, thumbnail }] }
}
```

## Deploy (Render)

1. Push this repo to GitHub.
2. Render → New → Blueprint → select this repo (uses `render.yaml`), or
   New → Web Service with build `pip install -r requirements.txt` and
   start `uvicorn main:app --host 0.0.0.0 --port $PORT`.
3. Set the `API_KEY` environment variable to a long random secret.
   All `/api/*` endpoints return 503 until it is set.
