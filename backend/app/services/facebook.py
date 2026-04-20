"""Facebook video search via a logged-in session, driven by Playwright.

Facebook's search page is a React shell — cookie-only curl/httpx approaches hit
HTTP 400 on mobile or get an empty HTML shell on desktop. Playwright launches
headless Chromium, loads the session cookies, renders the page, waits for the
async GraphQL hydration, then scrapes the rendered DOM.

Heavier than httpx (launches a browser per query), but this is the only path
that survives long enough to be useful. If Chromium or Playwright isn't
installed, or any step errors out, we fall back to the stub so the rest of the
pipeline still works.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from typing import Any
from urllib.parse import quote

from app.services.config_store import facebook_cookies

logger = logging.getLogger(__name__)

PAGE_SIZE = 10

_DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)

_FB_SEARCH_URL = "https://www.facebook.com/search/videos/?q={q}"


def is_stub_mode() -> bool:
    return not bool(facebook_cookies())


def search(query: str, page_token: str = "") -> tuple[list[dict[str, Any]], str]:
    if is_stub_mode():
        return _stub_search(query, page_token)
    try:
        return _scrape_search_playwright(query, page_token)
    except Exception as e:
        logger.exception("facebook playwright scrape failed; returning stub batch")
        stub, _ = _stub_search(query, page_token)
        for r in stub:
            r["description"] = f"[Facebook scrape failed: {e}] {r['description']}"
        return stub, ""


def _parse_cookie_header(header: str) -> list[dict[str, Any]]:
    """Split 'a=1; b=2' into Playwright cookie dicts."""
    out: list[dict[str, Any]] = []
    for pair in (header or "").split(";"):
        if "=" not in pair:
            continue
        name, value = pair.strip().split("=", 1)
        if not name:
            continue
        out.append(
            {
                "name": name.strip(),
                "value": value.strip(),
                "domain": ".facebook.com",
                "path": "/",
                "secure": True,
                "httpOnly": False,
                "sameSite": "None",
            }
        )
    return out


def _scrape_search_playwright(
    query: str, page_token: str
) -> tuple[list[dict[str, Any]], str]:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    cookies = _parse_cookie_header(facebook_cookies())
    if not cookies:
        raise RuntimeError("No Facebook cookies configured")

    url = _FB_SEARCH_URL.format(q=quote(query))
    results: list[dict[str, Any]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        try:
            context = browser.new_context(
                user_agent=_DESKTOP_UA,
                viewport={"width": 1280, "height": 900},
                locale="en-US",
            )
            context.add_cookies(cookies)
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            # If FB redirected us to login, cookies have been revoked.
            if "/login" in page.url or "login.php" in page.url:
                raise RuntimeError(
                    "Facebook redirected to login — cookies are expired/revoked. "
                    "Paste fresh cookies in Settings."
                )
            # Wait for at least one video card to hydrate.
            try:
                page.wait_for_selector('a[href*="/watch/?v="]', timeout=25_000)
            except PWTimeout:
                # Some accounts render /videos/<id> links instead of /watch/?v=
                try:
                    page.wait_for_selector('a[href*="/videos/"]', timeout=5_000)
                except PWTimeout:
                    logger.warning("playwright: no video anchors appeared for %s", query)
            # Let a couple more hydration ticks pass.
            page.wait_for_timeout(1500)
            raw = page.evaluate(_EXTRACT_JS)
            results = _normalize_raw(raw)
        finally:
            browser.close()

    start = int(page_token or "0")
    slice_ = results[start : start + PAGE_SIZE]
    next_tok = str(start + PAGE_SIZE) if start + PAGE_SIZE < len(results) else ""
    return slice_, next_tok


_EXTRACT_JS = """
() => {
  const items = [];
  const seen = new Set();
  const rx = /\\/(?:watch\\/?\\?v=|videos\\/)(\\d{6,})/;
  document.querySelectorAll('a[href*="/watch/?v="], a[href*="/videos/"]').forEach(a => {
    const href = a.href || '';
    const m = href.match(rx);
    if (!m) return;
    const vid = m[1];
    if (seen.has(vid)) return;
    seen.add(vid);

    // Walk up to the enclosing card-ish container to find title + thumbnail.
    let container = a;
    for (let i = 0; i < 6 && container.parentElement; i++) {
      container = container.parentElement;
      if (container.querySelector('img')) break;
    }
    const aria = a.getAttribute('aria-label') || '';
    const spanText = (a.innerText || '').trim();
    const fallbackTitle = (container.querySelector('span[dir="auto"]')?.innerText || '').trim();
    const title = aria || spanText || fallbackTitle || '';
    const thumb = container.querySelector('img')?.src || '';
    items.push({ vid, href, title: title.slice(0, 220), thumb });
  });
  return items;
}
"""


def _normalize_raw(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in raw or []:
        vid = str(r.get("vid") or "").strip()
        if not vid:
            continue
        title = (r.get("title") or "").strip() or f"Facebook video {vid}"
        out.append(
            {
                "provider_video_id": vid,
                "title": title,
                "channel": "",
                "description": "",
                "duration_sec": 0.0,
                "view_count": 0,
                "published_at": "",
                "thumbnail_url": r.get("thumb") or "",
                "source_url": f"https://www.facebook.com/watch/?v={vid}",
            }
        )
    return out


def download(source_url: str, out_path: str) -> None:
    """yt-dlp with the user's cookies converted to Netscape format."""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    cookies = facebook_cookies()
    cmd = ["yt-dlp", "--no-playlist", "--no-part", "-o", out_path]
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
