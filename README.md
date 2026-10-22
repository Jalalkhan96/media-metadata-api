# Media Metadata API

A metadata-only API for public media URLs. Send it a video link → get
back public metadata: title, duration, thumbnail, channel/uploader,
views, likes, upload date, description and the available quality/format
list (**labels only**).

> **Live:** https://media-metadata-api.onrender.com
> **Interactive docs (Swagger):** https://media-metadata-api.onrender.com/docs

## What it does NOT do

This API **never downloads media** and **never returns direct media or
stream URLs**. It reads the same public metadata a visitor's browser
already sees on the page. Format entries contain quality labels only
(`format_id`, resolution, codec names, file-size estimates) — every
media URL is stripped server-side.

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/` | – | API info and endpoint list |
| GET | `/health` | – | Health check → `{"status":"ok","version":"1.0.0"}` |
| GET | `/api/info?url=<media-url>` | `X-API-Key` | Metadata for one media URL |
| POST | `/api/info` | `X-API-Key` | Same, with JSON body `{"url": "..."}` |
| GET | `/api/search?q=<query>&limit=<1-20>` | `X-API-Key` | YouTube search → metadata list |

Supported sources: YouTube, TikTok, Reddit, Pinterest, Vimeo,
Dailymotion, X/Twitter, Instagram and 1000+ more sites (via yt-dlp
extraction, download disabled).

## Live-verified behaviour (2026-10-21)

| Case | Result |
|---|---|
| TikTok video link | ✅ Full metadata — title, duration, uploader, views, upload date, format list |
| YouTube search (`/api/search`) | ✅ Full results — titles, channels, views, durations, thumbnails |
| YouTube video link (`/api/info`) | ⚠️ Basic metadata via YouTube's **official oEmbed** endpoint — title, channel, thumbnail. YouTube blocks full metadata extraction from datacenter IP ranges ("Sign in to confirm you're not a bot"); the API detects this and falls back automatically, marking the response with `"metadata_source": "official-oembed"` |
| Missing / wrong API key | `401` |
| Server started without `API_KEY` set | `/api/*` returns `503` (fail-closed) |

## Example response — `GET /api/info`

```json
{
  "type": "video",
  "id": "7106594312292453675",
  "title": "how many frogs did you find? 🐸 ...",
  "duration_seconds": 24,
  "thumbnail": "https://...",
  "uploader": "tiktok",
  "channel": "tiktok",
  "view_count": 592300,
  "upload_date": "20220607",
  "platform": "TikTok",
  "source_url": "https://www.tiktok.com/@tiktok/video/7106594312292453675",
  "formats": [
    { "format_id": "...", "ext": "mp4", "width": 576, "height": 1024,
      "vcodec": "h264", "acodec": "aac", "has_video": true, "has_audio": true }
  ]
}
```

## Usage — curl

```bash
curl "https://media-metadata-api.onrender.com/api/info?url=https://www.tiktok.com/@tiktok/video/7106594312292453675" \
  -H "X-API-Key: YOUR_API_KEY"

curl "https://media-metadata-api.onrender.com/api/search?q=lofi%20beats&limit=3" \
  -H "X-API-Key: YOUR_API_KEY"
```

## Usage — Node.js

```js
const BASE = "https://media-metadata-api.onrender.com";
const KEY = process.env.METADATA_API_KEY; // keep the key secret — never commit it

async function getInfo(mediaUrl) {
  const res = await fetch(`${BASE}/api/info?url=${encodeURIComponent(mediaUrl)}`, {
    headers: { "X-API-Key": KEY },
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res.json();
}

async function searchYouTube(query, limit = 5) {
  const res = await fetch(`${BASE}/api/search?q=${encodeURIComponent(query)}&limit=${limit}`, {
    headers: { "X-API-Key": KEY },
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res.json(); // { query, count, results: [{ id, title, url, duration_seconds, channel, view_count, thumbnail }] }
}
```

## Notes

- **Free tier sleep:** the Render free instance sleeps after ~15 minutes
  without traffic. The first call afterwards can take 30–60 seconds
  (cold start); later calls are fast.
- **Playlists:** a playlist URL returns `{ "type": "playlist", ... }`
  with entry metadata (up to 50 entries).
- **Rate behaviour:** at most 3 metadata extractions run concurrently;
  each lookup times out at 60 s and returns a clear error instead of
  hanging.

## Deploy / update

The service is defined by `render.yaml` (Render Blueprint):

- Build: `pip install -r requirements.txt`
- Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Health check: `/health`
- Required env var: `API_KEY` (long random secret; set in the Render
  dashboard — **never** commit it to this repo)

Note: on this Blueprint, pushing to `main` does not always auto-deploy —
use **Manual Deploy → Deploy latest commit** in the Render dashboard
after pushing a change.

## Stack

FastAPI · uvicorn · yt-dlp (extract-only, `skip_download`) · curl-cffi
(for extractor impersonation) · official YouTube/TikTok oEmbed fallback
