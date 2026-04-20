"""Facebook video search via a user-supplied session cookie.

Facebook has no public keyword search API for videos. The operator pastes the
raw Cookie header from a logged-in session via Settings; we drive
facebook.com/search/videos/?q=... over HTTPS and extract embedded video objects
from the returned HTML shell.

This is fragile — Facebook regularly changes markup and may challenge the
session or ban the account. When it breaks, paste fresh cookies and we'll try
again. When no cookies are configured, returns a 10-entry stub so the rest of
the pipeline is testable.
"""

from __future__ import annotations

import logging
import re
import subprocess
from typing import Any
from urllib.parse import quote

import httpx

from app.services.config_store import facebook_cookies

logger = logging.getLogger(__name__)

PAGE_SIZE = 10
_FB_SEARCH_URL = "https://www.facebook.com/search/videos/?q={q}"


def is_stub_mode() -> bool:
    return not bool(facebook_cookies())


def search(query: str, page_token: str = "") -> tuple[list[dict[str, Any]], str]:
    if is_stub_mode():
        return _stub_search(query, page_token)
    try:
        return _scrape_search(query, page_token)
    except Exception as e:
        logger.exception("facebook scrape failed; returning stub batch")
        stub, _ = _stub_search(query, page_token)
        for r in stub:
            r["description"] = f"[Facebook scrape failed: {e}] {r['description']}"
        return stub, ""


def _scrape_search(query: str, page_token: str) -> tuple[list[dict[str, Any]], str]:
    cookies_header = facebook_cookies()
    url = _FB_SEARCH_URL.format(q=quote(query))
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
        ),
        "Cookie": cookies_header,
        "Accept-Language": "en-US,en;q=0.9",
    }
    with httpx.Client(follow_redirects=True, timeout=30, headers=headers) as c:
        r = c.get(url)
    if r.status_code == 302 or "login.php" in r.text[:2000]:
        raise RuntimeError(
            "Facebook redirected to login — cookies are missing/expired. "
            "Paste fresh cookies in Settings."
        )
    r.raise_for_status()
    html = r.text
    results = _parse_video_objects(html, query)
    # Facebook's search response is infinite-scroll GraphQL under the hood;
    # the HTML shell only gives us the first slate of results. Treat each
    # call as one page; no true next-token yet. Honest limitation.
    start = int(page_token or "0")
    slice_ = results[start : start + PAGE_SIZE]
    next_tok = str(start + PAGE_SIZE) if start + PAGE_SIZE < len(results) else ""
    return slice_, next_tok


_VIDEO_ID_RE = re.compile(r'"video_id"\s*:\s*"(\d+)"')
_TITLE_RE = re.compile(r'"video_title"\s*:\s*"([^"]{3,200})"')


def _parse_video_objects(html: str, query: str) -> list[dict[str, Any]]:
    ids = _VIDEO_ID_RE.findall(html)
    titles = _TITLE_RE.findall(html)
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for i, vid in enumerate(ids):
        if vid in seen:
            continue
        seen.add(vid)
        title = titles[i] if i < len(titles) else f"Facebook result #{i + 1} for '{query}'"
        out.append(
            {
                "provider_video_id": vid,
                "title": title,
                "channel": "",
                "description": "",
                "duration_sec": 0.0,
                "view_count": 0,
                "published_at": "",
                "thumbnail_url": "",
                "source_url": f"https://www.facebook.com/watch/?v={vid}",
            }
        )
    return out


def download(source_url: str, out_path: str) -> None:
    """yt-dlp supports Facebook watch URLs when supplied with the user's cookies."""
    import os
    import tempfile

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    cookies = facebook_cookies()
    cmd = ["yt-dlp", "--no-playlist", "--no-part", "-o", out_path]
    cleanup: list[str] = []
    if cookies:
        # yt-dlp wants cookies in Netscape format; pasted header is Key=Value;
        # Key=Value; — convert on the fly.
        tf = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, prefix="fbcookie_"
        )
        tf.write("# Netscape HTTP Cookie File\n")
        for pair in cookies.split(";"):
            if "=" not in pair:
                continue
            name, value = pair.strip().split("=", 1)
            tf.write(
                f".facebook.com\tTRUE\t/\tTRUE\t0\t{name.strip()}\t{value.strip()}\n"
            )
        tf.close()
        cleanup.append(tf.name)
        cmd.extend(["--cookies", tf.name])
    cmd.append(source_url)
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=900)
    finally:
        for p in cleanup:
            try:
                os.remove(p)
            except OSError:
                pass


# ──────────────────────────── stub ────────────────────────────


def _stub_search(query: str, page_token: str) -> tuple[list[dict[str, Any]], str]:
    page = int(page_token or "0")
    q = query.strip() or "videos"
    out: list[dict[str, Any]] = []
    for i in range(PAGE_SIZE):
        idx = page * PAGE_SIZE + i
        vid = f"{10_000_000_000_000 + idx}"
        out.append(
            {
                "provider_video_id": vid,
                "title": f"[FB stub] {q} — community clip #{idx + 1}",
                "channel": f"FacebookUser{idx % 23}",
                "description": "Simulated Facebook result. Paste session cookies in Settings for real search.",
                "duration_sec": float(120 + (idx % 5) * 60),
                "view_count": 2000 + idx * 75,
                "published_at": "2026-02-01T00:00:00Z",
                "thumbnail_url": f"https://picsum.photos/seed/fb{vid}/320/180",
                "source_url": f"https://www.facebook.com/watch/?v={vid}",
            }
        )
    next_tok = str(page + 1) if page < 3 else ""
    return out, next_tok
