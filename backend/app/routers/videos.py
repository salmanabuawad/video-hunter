from datetime import datetime
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.auth import get_current_user
from app.db import get_session
from app.models import Project, User, Video
from app.schemas import DecideIn, VideoOut

router = APIRouter(prefix="/api/videos", tags=["videos"])


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
    v = _assert_video_access(session, video_id, user)
    if not v.file_path or not os.path.exists(v.file_path):
        raise HTTPException(
            status_code=404,
            detail="File not on disk yet; the background download may still be running.",
        )
    filename = os.path.basename(v.file_path)
    return FileResponse(v.file_path, filename=filename, media_type="video/mp4")
