"""
Media Metadata API — metadata ONLY.

Given a public media URL (YouTube, TikTok, Reddit, Pinterest, Vimeo,
Dailymotion, X, Instagram and 1000+ other sites supported by yt-dlp),
returns public metadata: title, duration, thumbnail, uploader/channel,
views, upload date, description and the format/quality list (labels only).

This service NEVER downloads media and NEVER returns direct media/stream
URLs. All `url` fields inside format entries are stripped on purpose.
"""

import asyncio
import os
import secrets
from typing import Any, Optional
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel

API_KEY = os.environ.get("API_KEY", "")
VERSION = "1.0.0"

app = FastAPI(
    title="Media Metadata API",
    version=VERSION,
    description="Metadata-only lookup for public media URLs. No downloads, "
    "no direct media URLs — title, duration, thumbnail, channel, views, "
    "dates and quality labels only.",
)

_extract_lock = asyncio.Semaphore(3)

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


async def require_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    if not API_KEY:
        raise HTTPException(
            status_code=503,
            detail="API_KEY is not configured on the server.",
        )
    if not x_api_key or not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key.")


# ---------------------------------------------------------------------------
# URL validation
# ---------------------------------------------------------------------------


def validate_url(raw: str) -> str:
    url = (raw or "").strip()
    if not url or len(url) > 2048:
        raise HTTPException(status_code=400, detail="A valid URL is required.")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(
            status_code=400, detail="Only public http(s) URLs are accepted."
        )
    return url


# ---------------------------------------------------------------------------
# Metadata extraction (yt-dlp in extract-only mode — nothing is downloaded)
# ---------------------------------------------------------------------------

_YDL_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "noplaylist": True,
    "socket_timeout": 15,
    "retries": 1,
    "extract_flat": False,
}


def _extract_sync(url: str) -> dict[str, Any]:
    import yt_dlp

    with yt_dlp.YoutubeDL(_YDL_OPTS) as ydl:
        return ydl.extract_info(url, download=False)


def _search_sync(query: str, limit: int) -> dict[str, Any]:
    import yt_dlp

    opts = dict(_YDL_OPTS)
    opts["extract_flat"] = True
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(f"ytsearch{limit}:{query}", download=False)


def _clean_format(fmt: dict[str, Any]) -> dict[str, Any]:
    """Keep quality labels only — strip every URL / stream field."""
    keep = (
        "format_id",
        "ext",
        "format_note",
        "width",
        "height",
        "fps",
        "vcodec",
        "acodec",
        "filesize",
        "filesize_approx",
        "tbr",
        "abr",
        "vbr",
        "quality",
        "resolution",
        "aspect_ratio",
        "dynamic_range",
        "audio_channels",
    )
    out = {k: fmt.get(k) for k in keep if fmt.get(k) is not None}
    out["has_video"] = fmt.get("vcodec") not in (None, "none")
    out["has_audio"] = fmt.get("acodec") not in (None, "none")
    return out


def sanitize_info(info: dict[str, Any]) -> dict[str, Any]:
    """Whitelist public metadata. No media URLs, no captions, no manifests."""
    out: dict[str, Any] = {
        "id": info.get("id"),
        "title": info.get("title"),
        "description": (info.get("description") or "")[:2000] or None,
        "duration_seconds": info.get("duration"),
        "duration": info.get("duration_string"),
        "thumbnail": info.get("thumbnail"),
        "uploader": info.get("uploader"),
        "channel": info.get("channel"),
        "channel_url": info.get("channel_url") or info.get("uploader_url"),
        "channel_follower_count": info.get("channel_follower_count"),
        "view_count": info.get("view_count"),
        "like_count": info.get("like_count"),
        "comment_count": info.get("comment_count"),
        "upload_date": info.get("upload_date"),
        "release_date": info.get("release_date"),
        "platform": info.get("extractor"),
        "source_url": info.get("webpage_url") or info.get("original_url"),
        "categories": info.get("categories"),
        "tags": (info.get("tags") or [])[:20] or None,
        "age_limit": info.get("age_limit"),
        "is_live": info.get("is_live"),
        "was_live": info.get("was_live"),
        "availability": info.get("availability"),
        "width": info.get("width"),
        "height": info.get("height"),
        "fps": info.get("fps"),
        "formats": [
            _clean_format(f) for f in (info.get("formats") or []) if isinstance(f, dict)
        ],
    }
    return {k: v for k, v in out.items() if v is not None}


def sanitize_search_entry(entry: dict[str, Any]) -> dict[str, Any]:
    out = {
        "id": entry.get("id"),
        "title": entry.get("title"),
        "url": entry.get("url") or entry.get("webpage_url"),
        "duration_seconds": entry.get("duration"),
        "channel": entry.get("channel") or entry.get("uploader"),
        "channel_url": entry.get("channel_url") or entry.get("uploader_url"),
        "view_count": entry.get("view_count"),
        "thumbnail": None,
    }
    thumbs = entry.get("thumbnails") or []
    if thumbs:
        out["thumbnail"] = thumbs[-1].get("url")
    return {k: v for k, v in out.items() if v is not None}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "name": "Media Metadata API",
        "version": VERSION,
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "GET /health": "server health",
            "GET /api/info?url=<media-url>": "metadata for one media URL (X-API-Key required)",
            "POST /api/info": "same, JSON body {\"url\": \"...\"}",
            "GET /api/search?q=<query>&limit=<1-20>": "YouTube search metadata (X-API-Key required)",
        },
        "note": "Metadata only. This API does not download media and does "
        "not return direct media/stream URLs.",
    }


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "version": VERSION}


class InfoRequest(BaseModel):
    url: str


async def _do_info(url: str) -> dict[str, Any]:
    url = validate_url(url)
    async with _extract_lock:
        try:
            info = await asyncio.wait_for(
                asyncio.to_thread(_extract_sync, url), timeout=60
            )
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="Metadata lookup timed out.")
        except Exception as exc:  # yt-dlp raises DownloadError and friends
            raise HTTPException(
                status_code=422,
                detail=f"Could not read metadata for this URL: {exc.__class__.__name__}: {str(exc)[:300]}",
            )
    if info.get("_type") == "playlist":
        entries = [e for e in (info.get("entries") or []) if isinstance(e, dict)]
        return {
            "type": "playlist",
            "id": info.get("id"),
            "title": info.get("title"),
            "source_url": info.get("webpage_url"),
            "count": len(entries),
            "entries": [sanitize_search_entry(e) for e in entries[:50]],
        }
    result = sanitize_info(info)
    result["type"] = "video"
    return result


@app.get("/api/info", dependencies=[Depends(require_key)])
async def info_get(url: str = Query(..., description="Public media URL")):
    return await _do_info(url)


@app.post("/api/info", dependencies=[Depends(require_key)])
async def info_post(body: InfoRequest):
    return await _do_info(body.url)


@app.get("/api/search", dependencies=[Depends(require_key)])
async def search(
    q: str = Query(..., description="Search query (YouTube)"),
    limit: int = Query(5, ge=1, le=20),
):
    query = (q or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query is required.")
    async with _extract_lock:
        try:
            data = await asyncio.wait_for(
                asyncio.to_thread(_search_sync, query, limit), timeout=60
            )
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="Search timed out.")
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Search failed: {exc.__class__.__name__}: {str(exc)[:300]}",
            )
    entries = [e for e in (data.get("entries") or []) if isinstance(e, dict)]
    return {
        "query": query,
        "count": len(entries),
        "results": [sanitize_search_entry(e) for e in entries],
    }
