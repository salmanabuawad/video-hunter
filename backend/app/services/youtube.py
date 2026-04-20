"""YouTube Data API v3 search + yt-dlp download.

When no API key is configured, returns 10 fabricated results per call so the UI
and keep/reject flow is testable end-to-end without credentials. The stub uses
real YouTube-style IDs that yt-dlp would ignore; no network call is made.
"""

from __future__ import annotations

import logging
import re
import subprocess
from typing import Any

import httpx

from app.services.config_store import youtube_api_key

logger = logging.getLogger(__name__)

YT_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YT_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
PAGE_SIZE = 10


def is_stub_mode() -> bool:
    return not bool(youtube_api_key())


def search(query: str, page_token: str = "") -> tuple[list[dict[str, Any]], str]:
    """Return (results, next_page_token). Results shape matches what the
    router persists into the Video table."""
    if is_stub_mode():
        return _stub_search(query, page_token)
    key = youtube_api_key()
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": str(PAGE_SIZE),
        "key": key,
    }
    if page_token:
        params["pageToken"] = page_token
    r = httpx.get(YT_SEARCH_URL, params=params, timeout=30)
    r.raise_for_status()
    payload = r.json()
    items = payload.get("items") or []
    video_ids = [it["id"]["videoId"] for it in items if it.get("id", {}).get("videoId")]
    details = _fetch_details(video_ids, key) if video_ids else {}
    results: list[dict[str, Any]] = []
    for it in items:
        vid = it.get("id", {}).get("videoId")
        if not vid:
            continue
        sn = it.get("snippet") or {}
        det = details.get(vid, {})
        results.append(
            {
                "provider_video_id": vid,
                "title": sn.get("title") or "",
                "channel": sn.get("channelTitle") or "",
                "description": sn.get("description") or "",
                "duration_sec": det.get("duration_sec", 0.0),
                "view_count": det.get("view_count", 0),
                "published_at": sn.get("publishedAt") or "",
                "thumbnail_url": (sn.get("thumbnails", {}).get("medium") or {}).get("url") or "",
                "source_url": f"https://www.youtube.com/watch?v={vid}",
            }
        )
    return results, payload.get("nextPageToken", "") or ""


def _fetch_details(video_ids: list[str], key: str) -> dict[str, dict[str, Any]]:
    params = {
        "part": "contentDetails,statistics",
        "id": ",".join(video_ids),
        "key": key,
    }
    r = httpx.get(YT_VIDEOS_URL, params=params, timeout=30)
    if r.status_code != 200:
        logger.warning("youtube videos endpoint failed: %s %s", r.status_code, r.text[:300])
        return {}
    out: dict[str, dict[str, Any]] = {}
    for it in (r.json().get("items") or []):
        vid = it.get("id")
        if not vid:
            continue
        out[vid] = {
            "duration_sec": _iso8601_to_sec(
                (it.get("contentDetails") or {}).get("duration", "PT0S")
            ),
            "view_count": int((it.get("statistics") or {}).get("viewCount") or 0),
        }
    return out


_ISO_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def _iso8601_to_sec(s: str) -> float:
    m = _ISO_RE.fullmatch(s or "")
    if not m:
        return 0.0
    h, mn, sc = (int(x) if x else 0 for x in m.groups())
    return float(h * 3600 + mn * 60 + sc)


def download(source_url: str, out_path: str) -> None:
    """Use yt-dlp to pull the best <=720p mp4. Raises on failure."""
    import os

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    cmd = [
        "yt-dlp",
        "-f",
        "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best",
        "--merge-output-format",
        "mp4",
        "--no-playlist",
        "--no-part",
        "-o",
        out_path,
        source_url,
    ]
    logger.info("yt-dlp %s -> %s", source_url, out_path)
    subprocess.run(cmd, check=True, capture_output=True, timeout=600)


# ──────────────────────────── stub ────────────────────────────


_STUB_TEMPLATE = [
    ("Full tutorial — how to {q}", "TutorialHub", 724, 125400),
    ("{q} explained in 5 minutes", "QuickExplain", 312, 89200),
    ("Everything you need to know about {q}", "DeepDive", 892, 210300),
    ("Top 10 {q} tips for 2026", "TopListsDaily", 545, 67800),
    ("{q} — behind the scenes", "IndustryInsider", 1210, 45100),
    ("Is {q} worth it? Honest review", "ReviewBuddy", 478, 156700),
    ("Live stream: {q} Q&A", "AskTheExpert", 3600, 22800),
    ("{q} for beginners — step by step", "StartHere", 812, 94500),
    ("The science behind {q}", "ScienceNow", 636, 132000),
    ("Future of {q} — predictions", "TrendWatch", 402, 73900),
]


def _stub_search(query: str, page_token: str) -> tuple[list[dict[str, Any]], str]:
    page = int(page_token or "0")
    results: list[dict[str, Any]] = []
    q = query.strip() or "videos"
    for i, (title, channel, dur, views) in enumerate(_STUB_TEMPLATE):
        idx = page * PAGE_SIZE + i
        vid = f"stub{idx:04d}{(hash(query) & 0xFFFFFFFF):08x}"[:11]
        results.append(
            {
                "provider_video_id": vid,
                "title": title.format(q=q),
                "channel": channel,
                "description": f"Simulated result #{idx + 1} for query '{q}'. Configure YOUTUBE_API_KEY in Settings to replace with live results.",
                "duration_sec": float(dur + (idx % 7) * 13),
                "view_count": views + idx * 1000,
                "published_at": "2026-01-01T00:00:00Z",
                "thumbnail_url": f"https://picsum.photos/seed/{vid}/320/180",
                "source_url": f"https://www.youtube.com/watch?v={vid}",
            }
        )
    next_tok = str(page + 1) if page < 4 else ""
    return results, next_tok
