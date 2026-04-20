"""Thin wrapper around the `app_config` table for provider keys/cookies."""

from datetime import datetime

from sqlmodel import Session, select

from app.db import engine
from app.models import AppConfig

KEY_YOUTUBE_API_KEY = "youtube_api_key"
KEY_FACEBOOK_COOKIES = "facebook_cookies"


def _get(key: str) -> str:
    with Session(engine) as s:
        row = s.exec(select(AppConfig).where(AppConfig.key == key)).first()
        return (row.value if row else "").strip()


def _set(key: str, value: str) -> None:
    with Session(engine) as s:
        row = s.exec(select(AppConfig).where(AppConfig.key == key)).first()
        if row:
            row.value = value
            row.updated_at = datetime.utcnow()
            s.add(row)
        else:
            s.add(AppConfig(key=key, value=value, updated_at=datetime.utcnow()))
        s.commit()


def youtube_api_key() -> str:
    return _get(KEY_YOUTUBE_API_KEY)


def set_youtube_api_key(value: str) -> None:
    _set(KEY_YOUTUBE_API_KEY, value.strip())


def facebook_cookies() -> str:
    """Raw Cookie header value, e.g. 'c_user=...; xs=...;'. Pasted by the
    operator via the Settings page."""
    return _get(KEY_FACEBOOK_COOKIES)


def set_facebook_cookies(value: str) -> None:
    _set(KEY_FACEBOOK_COOKIES, value.strip())
