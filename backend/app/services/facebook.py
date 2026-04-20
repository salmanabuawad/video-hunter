"""Facebook adapter — thin shim over facebook_video_search.

Reads cookies + optional email/password from app_config, runs the Playwright
scraper for both video and reel URLs, merges the results into the row shape
the router persists. Falls back to a 10-row stub whenever no credentials are
configured OR the live scrape raises.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
from typing import Any

from app.services.config_store import (
    facebook_cookies,
    facebook_email,
    facebook_password,
)
from app.services.facebook_video_search import FacebookVideoScraperSync

logger = logging.getLogger(__name__)

PAGE_SIZE = 10


def is_stub_mode() -> bool:
    """True when we have no way to authenticate with Facebook."""
    return not (facebook_cookies() or (facebook_email() and facebook_password()))


# ──────────────────────────── search ────────────────────────────


def search(query: str, page_token: str = "") -> tuple[list[dict[str, Any]], str]:
    """Return (batch, next_page_token). Pagination is local: we fetch a pool of
    results once and the router walks through it PAGE_SIZE at a time.

    On scrape failure we raise RuntimeError with a human-readable reason. We
    deliberately do NOT hide failures behind fake stub rows — that bug made
    operators think results were live when the scraper had actually died.
    The router turns this exception into an HTTP 502 that the UI surfaces
    as a banner on an otherwise-empty grid.
    """
    if is_stub_mode():
        return _stub_search(query, page_token)
    try:
        return _live_search(query, page_token)
    except Exception as e:
        logger.exception("facebook live scrape failed")
        raise RuntimeError(f"Facebook scrape failed: {e}") from e


def _live_search(query: str, page_token: str) -> tuple[list[dict[str, Any]], str]:
    cookies = facebook_cookies()
    email = facebook_email()
    password = facebook_password()

    # Harvest enough rows in one browser launch to cover several "Next" pages.
    pool_size = PAGE_SIZE * 4

    with FacebookVideoScraperSync(headless=True) as fb:
        if cookies:
            fb.load_cookies(cookies)
        elif email and password:
            if not fb.login(email, password):
                raise RuntimeError(
                    "Facebook login failed (checkpoint, 2FA, or wrong password). "
                    "Paste fresh session cookies in Settings."
                )
        videos = fb.search_videos(query, max_results=pool_size)
        reels = fb.search_reels(query, max_results=pool_size)

    merged = _merge(videos, reels)
    start = int(page_token or "0")
    slice_ = merged[start : start + PAGE_SIZE]
    next_tok = str(start + PAGE_SIZE) if start + PAGE_SIZE < len(merged) else ""
    return [_to_row(r) for r in slice_], next_tok


def _merge(
    videos: list[dict[str, Any]], reels: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Interleave videos+reels; dedupe by canonical URL."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pair in zip(videos, reels):  # round-robin pairs
        for item in pair:
            url = item.get("url") or ""
            if url and url not in seen:
                seen.add(url)
                out.append(item)
    # Append any remaining after the shorter list ran out.
    for item in videos[len(reels) :] + reels[len(videos) :]:
        url = item.get("url") or ""
        if url and url not in seen:
            seen.add(url)
            out.append(item)
    return out


def _to_row(item: dict[str, Any]) -> dict[str, Any]:
    """Convert a scraper VideoResult dict to the shape the router persists."""
    kind = item.get("type") or "video"
    title = item.get("title") or ""
    vid = item.get("provider_video_id") or ""
    url = item.get("url") or ""
    return {
        "provider_video_id": vid,
        "title": f"[{kind}] {title}" if kind == "reel" else title,
        "channel": "",
        "description": "",
        "duration_sec": 0.0,
        "view_count": 0,
        "published_at": "",
        "thumbnail_url": item.get("thumbnail") or "",
        "source_url": url,
    }


# ──────────────────────────── download ────────────────────────────


def download(source_url: str, out_path: str) -> None:
    """yt-dlp with the user's cookies converted to Netscape format.

    Invokes yt_dlp via `sys.executable -m` so the systemd service's PATH
    doesn't need to include the venv's bin dir.
    """
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    cookies = facebook_cookies()
    cmd: list[str] = [
        sys.executable, "-m", "yt_dlp",
        "--no-playlist", "--no-part", "-o", out_path,
    ]
    cleanup: list[str] = []
    if cookies:
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
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or b"").decode("utf-8", errors="replace")[:2000]
        raise RuntimeError(f"yt-dlp failed ({e.returncode}): {stderr}") from e
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
        kind = "reel" if i % 3 == 2 else "video"
        out.append(
            {
                "provider_video_id": vid,
                "title": f"[{kind}] [FB stub] {q} — community clip #{idx + 1}",
                "channel": f"FacebookUser{idx % 23}",
                "description": "Simulated Facebook result. Paste session cookies in Settings for real search.",
                "duration_sec": float(120 + (idx % 5) * 60),
                "view_count": 2000 + idx * 75,
                "published_at": "2026-02-01T00:00:00Z",
                "thumbnail_url": f"https://picsum.photos/seed/fb{vid}/320/180",
                "source_url": (
                    f"https://www.facebook.com/reel/{vid}"
                    if kind == "reel"
                    else f"https://www.facebook.com/watch/?v={vid}"
                ),
            }
        )
    next_tok = str(page + 1) if page < 3 else ""
    return out, next_tok
