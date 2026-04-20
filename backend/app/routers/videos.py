from datetime import datetime
import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.auth import get_current_user
from app.config import DOWNLOAD_DIR
from app.db import get_session
from app.models import Project, User, Video
from app.schemas import DecideIn, VideoOut
from app.services import facebook as fb_svc
from app.services import youtube as yt_svc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/videos", tags=["videos"])

_PROVIDERS = {"youtube": yt_svc, "facebook": fb_svc}


def _safe_name(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in s[:60]) or "video"


def _ensure_local_file(session: Session, v: Video) -> str:
    """Return the local path of the video, running yt-dlp on demand if needed."""
    if v.file_path and os.path.exists(v.file_path):
        return v.file_path
    adapter = _PROVIDERS.get(v.provider)
    if not adapter:
        raise HTTPException(status_code=400, detail=f"No downloader for provider {v.provider!r}")
    out_dir = os.path.join(DOWNLOAD_DIR, str(v.project_id))
    fname = f"{v.provider}_{v.provider_video_id}_{_safe_name(v.title)}.mp4"
    out_path = os.path.abspath(os.path.join(out_dir, fname))
    try:
        adapter.download(v.source_url, out_path)
    except Exception as e:
        logger.exception("on-demand download failed for video %s", v.id)
        raise HTTPException(status_code=502, detail=f"Download failed: {e}") from e
    if not os.path.exists(out_path):
        raise HTTPException(status_code=502, detail="Downloader claimed success but file is missing")
    v.file_path = out_path
    session.add(v)
    session.commit()
    session.refresh(v)
    return out_path


def _assert_video_access(session: Session, video_id: int, user: User) -> Video:
    video = session.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    project = session.get(Project, video.project_id)
    if user.role != "admin" and (not project or project.owner_id != user.id):
        raise HTTPException(status_code=403, detail="Not your video")
    return video


@router.put("/{video_id}/decide", response_model=VideoOut)
def decide(
    video_id: int,
    body: DecideIn,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    v = _assert_video_access(session, video_id, user)
    decision = (body.decision or "").strip().lower()
    if decision not in ("keep", "reject", "candidate"):
        raise HTTPException(status_code=400, detail="decision must be keep|reject|candidate")
    v.state = decision
    v.decided_at = datetime.utcnow() if decision != "candidate" else None
    session.add(v)
    session.commit()
    session.refresh(v)
    has_file = bool(v.file_path) and os.path.exists(v.file_path)
    return VideoOut.model_validate(
        {
            **v.model_dump(),
            "has_local_file": has_file,
            "download_url": f"/api/videos/{v.id}/download" if has_file else None,
        }
    )


@router.get("/{video_id}/download")
def download(
    video_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Stream the video to the client. If we haven't pulled it yet, do the
    yt-dlp download synchronously and then stream. The browser sees one long
    request; Nginx proxy_read_timeout (600s) covers typical sizes."""
    v = _assert_video_access(session, video_id, user)
    path = _ensure_local_file(session, v)
    filename = os.path.basename(path)
    return FileResponse(path, filename=filename, media_type="video/mp4")
