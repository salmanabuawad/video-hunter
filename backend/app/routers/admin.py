from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.auth import require_admin
from app.db import get_session
from app.models import User
from app.schemas import AppConfigIn, AppConfigStatus
from app.services.config_store import (
    facebook_cookies,
    set_facebook_cookies,
    set_youtube_api_key,
    youtube_api_key,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/config/status", response_model=AppConfigStatus)
def get_config_status(user: User = Depends(require_admin)):
    return AppConfigStatus(
        youtube_configured=bool(youtube_api_key()),
        facebook_configured=bool(facebook_cookies()),
    )


@router.post("/config", response_model=AppConfigStatus)
def save_config(
    body: AppConfigIn,
    session: Session = Depends(get_session),
    user: User = Depends(require_admin),
):
    """Empty fields leave existing values untouched (so an admin can update one
    provider without re-pasting the other)."""
    if body.youtube_api_key is not None and body.youtube_api_key.strip():
        set_youtube_api_key(body.youtube_api_key.strip())
    if body.facebook_cookies is not None and body.facebook_cookies.strip():
        set_facebook_cookies(body.facebook_cookies.strip())
    return AppConfigStatus(
        youtube_configured=bool(youtube_api_key()),
        facebook_configured=bool(facebook_cookies()),
    )
