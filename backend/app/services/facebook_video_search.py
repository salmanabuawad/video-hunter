"""
Facebook video + reel search via Playwright.

Public surface:
    FacebookVideoScraper                 — async scraper class (context manager)
    FacebookVideoScraperSync             — sync wrapper over the async class
    search_videos(query, max_results=20) — sync convenience function
    search_reels(query, max_results=20)  — sync convenience function
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
from dataclasses import asdict, dataclass, field
from types import TracebackType
from typing import Any, Awaitable, Callable, Iterable, Optional, TypeVar
from urllib.parse import quote, urlparse

from playwright.async_api import (
    Browser,
    BrowserContext,
    Error as PWError,
    Page,
    Playwright,
    TimeoutError as PWTimeoutError,
    async_playwright,
)

logger = logging.getLogger(__name__)

SEARCH_URL_VIDEOS = "https://www.facebook.com/watch/search/?q={q}"
# Facebook has no dedicated "reels only" search; generic posts search surfaces
# reel cards mixed with other post types, and we filter by URL shape.
SEARCH_URL_REELS = "https://www.facebook.com/search/posts/?q={q}"
LOGIN_URL = "https://www.facebook.com/login.php"

DEFAULT_VIEWPORT = {"width": 1366, "height": 900}
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)

RE_WATCH = re.compile(r"^/watch/?(?:\?v=|/)?(\d{6,})", re.IGNORECASE)
RE_VIDEO_PHP = re.compile(r"^/video\.php.*?v=(\d{6,})", re.IGNORECASE)
RE_VIDEOS_PATH = re.compile(r"^/[^/]+/videos/(\d{6,})", re.IGNORECASE)
RE_REEL = re.compile(r"^/reel/(\d{6,})", re.IGNORECASE)
RE_REELS = re.compile(r"^/reels/(?:video/)?(\d{6,})", re.IGNORECASE)

VIDEO_PATTERNS = (RE_WATCH, RE_VIDEO_PHP, RE_VIDEOS_PATH)
REEL_PATTERNS = (RE_REEL, RE_REELS)


@dataclass(frozen=True)
class VideoResult:
    type: str  # "video" | "reel"
    title: str
    url: str
    provider_video_id: str = ""
    thumbnail: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


T = TypeVar("T")


async def _with_retry(
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    label: str = "op",
    base_delay: float = 1.0,
) -> T:
    last_exc: Optional[BaseException] = None
    for i in range(1, attempts + 1):
        try:
            return await fn()
        except (PWTimeoutError, PWError) as e:
            last_exc = e
            if i == attempts:
                break
            delay = base_delay * (2 ** (i - 1)) + random.uniform(0, 0.5)
            logger.warning("%s failed (attempt %d/%d): %s; retry in %.1fs", label, i, attempts, e, delay)
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc


def _classify(path: str) -> Optional[tuple[str, str]]:
    for rx in REEL_PATTERNS:
        m = rx.search(path)
        if m:
            return "reel", m.group(1)
    for rx in VIDEO_PATTERNS:
        m = rx.search(path)
        if m:
            return "video", m.group(1)
    return None


def _parse_cookie_header(header: str) -> list[dict[str, Any]]:
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


class FacebookVideoScraper:
    """Async scraper for Facebook Watch search + reels search.

    Typical lifecycle:
        async with FacebookVideoScraper(headless=True) as fb:
            await fb.load_cookies(cookie_header)   # or fb.login(email, password)
            videos = await fb.search_videos("query", max_results=20)
            reels  = await fb.search_reels("query",  max_results=20)

    Unauthenticated requests hit Facebook's login wall quickly; supply
    cookies or login credentials before searching.
    """

    def __init__(
        self,
        headless: bool = True,
        user_agent: str = DEFAULT_USER_AGENT,
        viewport: Optional[dict[str, int]] = None,
        locale: str = "en-US",
        default_timeout_ms: int = 30_000,
        navigation_timeout_ms: int = 45_000,
        scroll_rounds: int = 10,
        scroll_pause_ms: int = 900,
        proxy: Optional[dict[str, str]] = None,
    ) -> None:
        self.headless = headless
        self.user_agent = user_agent
        self.viewport = viewport or DEFAULT_VIEWPORT
        self.locale = locale
        self.default_timeout_ms = default_timeout_ms
        self.navigation_timeout_ms = navigation_timeout_ms
        self.scroll_rounds = scroll_rounds
        self.scroll_pause_ms = scroll_pause_ms
        self.proxy = proxy

        self._pw: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    async def __aenter__(self) -> "FacebookVideoScraper":
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        await self.close()

    async def start(self) -> None:
        if self._context is not None:
            return
        self._pw = await async_playwright().start()
        launch_kwargs: dict[str, Any] = {
            "headless": self.headless,
            "args": [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        }
        if self.proxy:
            launch_kwargs["proxy"] = self.proxy
        self._browser = await self._pw.chromium.launch(**launch_kwargs)
        self._context = await self._browser.new_context(
            user_agent=self.user_agent,
            viewport=self.viewport,
            locale=self.locale,
        )
        self._context.set_default_timeout(self.default_timeout_ms)
        self._context.set_default_navigation_timeout(self.navigation_timeout_ms)
        logger.info("browser started (headless=%s)", self.headless)

    async def close(self) -> None:
        try:
            if self._context is not None:
                await self._context.close()
        finally:
            try:
                if self._browser is not None:
                    await self._browser.close()
            finally:
                if self._pw is not None:
                    await self._pw.stop()
                self._context = self._browser = self._pw = None

    async def load_cookies(self, cookie_header: str) -> None:
        self._assert_started()
        cookies = _parse_cookie_header(cookie_header)
        if not cookies:
            raise ValueError("cookie_header produced no cookies; check format")
        assert self._context is not None
        await self._context.add_cookies(cookies)
        logger.info("loaded %d cookies", len(cookies))

    async def login(self, email: str, password: str) -> bool:
        self._assert_started()
        assert self._context is not None
        if not email or not password:
            raise ValueError("email and password are required")

        async def _do_login() -> bool:
            assert self._context is not None
            page = await self._context.new_page()
            try:
                await page.goto(LOGIN_URL, wait_until="domcontentloaded")
                await page.fill("input[name='email']", email)
                await page.fill("input[name='pass']", password)
                async with page.expect_navigation(
                    wait_until="domcontentloaded", timeout=self.navigation_timeout_ms
                ):
                    await page.click("button[name='login']")
                if "login" in page.url or "checkpoint" in page.url:
                    logger.error("login blocked — url=%s", page.url)
                    return False
                cookies = await self._context.cookies("https://www.facebook.com")
                ok = any(c.get("name") == "c_user" for c in cookies)
                logger.info("login %s (c_user cookie %s)", "ok" if ok else "failed", "present" if ok else "missing")
                return ok
            finally:
                await page.close()

        return await _with_retry(_do_login, attempts=2, label="login")

    async def search_videos(self, query: str, max_results: int = 20) -> list[VideoResult]:
        return await self._search(query, SEARCH_URL_VIDEOS, keep_types={"video"}, max_results=max_results)

    async def search_reels(self, query: str, max_results: int = 20) -> list[VideoResult]:
        return await self._search(query, SEARCH_URL_REELS, keep_types={"reel"}, max_results=max_results)

    async def _search(
        self,
        query: str,
        url_template: str,
        keep_types: Iterable[str],
        max_results: int,
    ) -> list[VideoResult]:
        self._assert_started()
        if not query or not query.strip():
            raise ValueError("query is required")
        if max_results <= 0:
            return []
        keep = set(keep_types)
        target_url = url_template.format(q=quote(query.strip()))
        logger.info("search for %r, want up to %d %s result(s)", query, max_results, sorted(keep))

        async def _run() -> list[VideoResult]:
            assert self._context is not None
            page = await self._context.new_page()
            try:
                await page.goto(target_url, wait_until="domcontentloaded")
                if "/login" in page.url or "login.php" in page.url:
                    raise RuntimeError(
                        "Facebook redirected to login — session is not authenticated. "
                        "Call login() or load_cookies() first."
                    )
                try:
                    await page.wait_for_selector(
                        'a[href*="/watch/?v="], a[href*="/watch/"], a[href*="/videos/"], '
                        'a[href*="/reel/"], a[href*="/reels/"]',
                        timeout=15_000,
                    )
                except PWTimeoutError:
                    logger.info("no anchors after initial load; continuing to scroll")

                collected: dict[str, VideoResult] = {}
                stagnant = 0
                for round_idx in range(self.scroll_rounds + 1):
                    batch = await self._extract_current(page, keep)
                    before = len(collected)
                    for r in batch:
                        collected.setdefault(r.url, r)
                    added = len(collected) - before
                    logger.debug(
                        "round=%d batch=%d new=%d total=%d", round_idx, len(batch), added, len(collected)
                    )
                    if len(collected) >= max_results:
                        break
                    if round_idx == self.scroll_rounds:
                        break
                    if added == 0:
                        stagnant += 1
                        if stagnant >= 2:
                            logger.info("no new results for 2 rounds; stopping early")
                            break
                    else:
                        stagnant = 0
                    await self._scroll(page)

                ordered = list(collected.values())[:max_results]
                logger.info("collected %d result(s) for %r", len(ordered), query)
                return ordered
            finally:
                await page.close()

        return await _with_retry(_run, attempts=2, label="search")

    async def _scroll(self, page: Page) -> None:
        try:
            await page.mouse.wheel(0, 1800)
            await page.wait_for_timeout(self.scroll_pause_ms)
        except PWError as e:
            logger.debug("scroll noop: %s", e)

    async def _extract_current(self, page: Page, keep: set[str]) -> list[VideoResult]:
        raw = await page.evaluate(_EXTRACT_JS)
        out: list[VideoResult] = []
        for item in raw or []:
            href = str(item.get("href") or "")
            if not href:
                continue
            try:
                path = urlparse(href).path
            except Exception:
                continue
            classified = _classify(path)
            if classified is None:
                continue
            kind, vid = classified
            if kind not in keep:
                continue
            title = (item.get("title") or "").strip() or f"Facebook {kind} {vid}"
            canonical = (
                f"https://www.facebook.com/reel/{vid}"
                if kind == "reel"
                else f"https://www.facebook.com/watch/?v={vid}"
            )
            out.append(
                VideoResult(
                    type=kind,
                    title=title[:240],
                    url=canonical,
                    provider_video_id=vid,
                    thumbnail=str(item.get("thumb") or ""),
                )
            )
        return out

    def _assert_started(self) -> None:
        if self._context is None:
            raise RuntimeError("Scraper is not started; use `async with` or call start()")


_EXTRACT_JS = r"""
() => {
  const items = [];
  const seen = new Set();
  const isDuration = (s) => /^\d{1,3}(:\d{2}){1,2}$/.test((s || '').trim());

  const anchors = document.querySelectorAll(
    'a[href*="/watch/?v="], a[href*="/watch/"], a[href*="/videos/"], ' +
    'a[href*="/video.php"], a[href*="/reel/"], a[href*="/reels/"]'
  );

  anchors.forEach(a => {
    const href = a.href || '';
    if (!href || seen.has(href)) return;
    seen.add(href);

    let container = a;
    for (let i = 0; i < 10 && container.parentElement; i++) {
      container = container.parentElement;
      const role = container.getAttribute && container.getAttribute('role');
      if (role === 'article' || container.tagName === 'ARTICLE') break;
      if (container.querySelector('img') && (container.innerText || '').length > 40) break;
    }

    const candidates = [];
    const aria = a.getAttribute('aria-label');
    if (aria) candidates.push(aria);
    candidates.push(
      ...Array.from(container.querySelectorAll('h2, h3, h4')).map(n => n.innerText || '')
    );
    candidates.push(
      ...Array.from(container.querySelectorAll('span[dir="auto"]')).map(n => n.innerText || '')
    );
    candidates.push((a.innerText || '').trim());

    let title = '';
    for (const c of candidates) {
      const t = (c || '').replace(/\s+/g, ' ').trim();
      if (!t || isDuration(t) || t.length < 6) continue;
      title = t.slice(0, 240);
      break;
    }

    const img = container.querySelector('img[src^="http"]');
    items.push({ href, title, thumb: img ? img.src : '' });
  });
  return items;
}
"""


class FacebookVideoScraperSync:
    """Sync-friendly wrapper — spins up its own asyncio loop.

    Use from FastAPI background tasks, scripts, or any sync code.
    """

    def __init__(self, **scraper_kwargs: Any) -> None:
        self._inner = FacebookVideoScraper(**scraper_kwargs)
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def __enter__(self) -> "FacebookVideoScraperSync":
        self.start()
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        self.close()

    def start(self) -> None:
        self._ensure_loop()
        assert self._loop is not None
        self._loop.run_until_complete(self._inner.start())

    def close(self) -> None:
        if self._loop is None:
            return
        try:
            self._loop.run_until_complete(self._inner.close())
        finally:
            self._loop.close()
            self._loop = None

    def load_cookies(self, cookie_header: str) -> None:
        self._run(self._inner.load_cookies(cookie_header))

    def login(self, email: str, password: str) -> bool:
        return self._run(self._inner.login(email, password))

    def search_videos(self, query: str, max_results: int = 20) -> list[dict[str, Any]]:
        rows = self._run(self._inner.search_videos(query, max_results))
        return [r.to_dict() for r in rows]

    def search_reels(self, query: str, max_results: int = 20) -> list[dict[str, Any]]:
        rows = self._run(self._inner.search_reels(query, max_results))
        return [r.to_dict() for r in rows]

    def _ensure_loop(self) -> None:
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()

    def _run(self, coro: Awaitable[T]) -> T:
        self._ensure_loop()
        assert self._loop is not None
        return self._loop.run_until_complete(coro)


def _authenticate(
    fb: FacebookVideoScraperSync,
    email: Optional[str],
    password: Optional[str],
    cookie_header: Optional[str],
) -> None:
    if cookie_header:
        fb.load_cookies(cookie_header)
        return
    if email and password:
        ok = fb.login(email, password)
        if not ok:
            logger.warning("login() returned False; expect a login wall on the next nav")
        return
    logger.warning("no auth provided — search will hit a login wall")


def search_videos(
    query: str,
    max_results: int = 20,
    *,
    email: Optional[str] = None,
    password: Optional[str] = None,
    cookie_header: Optional[str] = None,
    headless: bool = True,
) -> list[dict[str, Any]]:
    """One-shot video search. Opens a browser, searches, returns dicts, tears down."""
    with FacebookVideoScraperSync(headless=headless) as fb:
        _authenticate(fb, email, password, cookie_header)
        return fb.search_videos(query, max_results=max_results)


def search_reels(
    query: str,
    max_results: int = 20,
    *,
    email: Optional[str] = None,
    password: Optional[str] = None,
    cookie_header: Optional[str] = None,
    headless: bool = True,
) -> list[dict[str, Any]]:
    """One-shot reel search. Opens a browser, searches, returns dicts, tears down."""
    with FacebookVideoScraperSync(headless=headless) as fb:
        _authenticate(fb, email, password, cookie_header)
        return fb.search_reels(query, max_results=max_results)


def main() -> None:
    """CLI smoke-test: python -m app.services.facebook_video_search <query>"""
    import argparse
    import json
    import os

    parser = argparse.ArgumentParser(description="Facebook video/reel search via Playwright")
    parser.add_argument("query", nargs="?", default="soil stabilization")
    parser.add_argument("--max", type=int, default=10)
    parser.add_argument("--no-headless", action="store_true")
    parser.add_argument("--email", default=os.environ.get("FB_EMAIL"))
    parser.add_argument("--password", default=os.environ.get("FB_PASSWORD"))
    parser.add_argument("--cookies", default=os.environ.get("FB_COOKIES"))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    with FacebookVideoScraperSync(headless=not args.no_headless) as fb:
        _authenticate(fb, args.email, args.password, args.cookies)
        out = {
            "query": args.query,
            "videos": fb.search_videos(args.query, max_results=args.max),
            "reels": fb.search_reels(args.query, max_results=args.max),
        }
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
