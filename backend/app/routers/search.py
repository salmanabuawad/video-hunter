"""Start a search for a project or advance to the next batch of 10 candidates.

Behaviour:
- POST /api/projects/{id}/search
  Body: {subject, provider}. Creates/updates the Search row, fetches the first
  10 candidates, persists them as Video rows with state="candidate", kicks off
  background downloads, and returns the batch.
- POST /api/projects/{id}/search/next
  Requires a prior search. Purges any candidates from the previous batch that
  the user did NOT mark as "keep" (DB row + file on disk), then fetches the
  next 10 using the persisted page_token_next. If there's no next token, 400.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session, select

from app.auth import get_current_user
from app.config import DOWNLOAD_DIR
from app.db import engine as db_engine, get_session
from app.models import Project, Search, User, Video
from app.schemas import SearchBatchOut, SearchStartIn, VideoOut
from app.services import facebook as fb_svc
from app.services import youtube as yt_svc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects", tags=["search"])


PROVIDERS = {"youtube": yt_svc, "facebook": fb_svc}


def _assert_project_access(session: Session, project_id: int, user: User) -> Project:
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if user.role != "admin" and project.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not your project")
    return project


def _provider_for(name: str):
    adapter = PROVIDERS.get((name or "").strip().lower())
    if not adapter:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider {name!r}; use one of: {list(PROVIDERS)}",
        )
    return adapter


def _persist_batch(
    session: Session,
    search: Search,
    items: list[dict],
) -> list[Video]:
    saved: list[Video] = []
    for item in items:
        existing = session.exec(
            select(Video).where(
                Video.project_id == search.project_id,
                Video.provider == search.provider,
                Video.provider_video_id == item["provider_video_id"],
            )
        ).first()
        if existing:
            saved.append(existing)
            continue
        v = Video(
            project_id=search.project_id,
            search_id=search.id,
            provider=search.provider,
            **item,
        )
        session.add(v)
        session.commit()
        session.refresh(v)
        saved.append(v)
    return saved


def _download_in_background(video_id: int) -> None:
    """Best-effort download; any failure just leaves file_path empty."""
    with Session(db_engine) as s:
        v = s.get(Video, video_id)
        if not v or v.state == "purged":
            return
        adapter = PROVIDERS.get(v.provider)
        if not adapter:
            return
        out_dir = os.path.join(DOWNLOAD_DIR, str(v.project_id))
        safe_title = "".join(
            c if c.isalnum() or c in "-_" else "_" for c in v.title[:60]
        ) or f"vid_{v.id}"
        out_path = os.path.abspath(
            os.path.join(out_dir, f"{v.provider}_{v.provider_video_id}_{safe_title}.mp4")
        )
        try:
            adapter.download(v.source_url, out_path)
            v.file_path = out_path
            s.add(v)
            s.commit()
        except Exception as e:
            logger.warning("download failed video_id=%s: %s", video_id, e)


def _purge_non_kept(session: Session, search: Search) -> int:
    """Delete every row from the most recent batch that is NOT marked 'keep'
    — that includes 'candidate' (unreviewed) and 'rejected' / legacy 'reject'.
    Returns how many rows were purged."""
    rows = session.exec(
        select(Video).where(
            Video.search_id == search.id, Video.state != "keep"
        )
    ).all()
    purged = 0
    for v in rows:
        if v.file_path and os.path.exists(v.file_path):
            try:
                os.remove(v.file_path)
            except OSError:
                pass
        session.delete(v)
        purged += 1
    session.commit()
    return purged


def _as_video_out(v: Video) -> VideoOut:
    has_file = bool(v.file_path) and os.path.exists(v.file_path)
    return VideoOut.model_validate(
        {
            **v.model_dump(),
            "has_local_file": has_file,
            "download_url": f"/api/videos/{v.id}/download" if has_file else None,
        }
    )


@router.post("/{project_id}/search", response_model=SearchBatchOut)
def start_search(
    project_id: int,
    body: SearchStartIn,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    project = _assert_project_access(session, project_id, user)
    query = body.subject.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Subject is required")
    provider_name = (body.provider or "youtube").strip().lower()
    adapter = _provider_for(provider_name)

    # Reuse a search row if the same (provider, query) already exists for the
    # project; otherwise create a new one. Reset page state to the beginning.
    search = session.exec(
        select(Search).where(
            Search.project_id == project_id,
            Search.provider == provider_name,
            Search.query == query,
        )
    ).first()
    if search is None:
        search = Search(project_id=project_id, provider=provider_name, query=query)
        session.add(search)
        session.commit()
        session.refresh(search)
    else:
        # Purge any outstanding candidates from the previous run so the user
        # starts clean.
        _purge_non_kept(session, search)
        search.page_token_current = ""
        search.page_token_next = ""
        search.total_fetched = 0

    try:
        items, next_token = adapter.search(query, "")
    except RuntimeError as e:
        # Scraper failed (login wall, Facebook layout change, etc.). Surface
        # the real reason via 502 so the UI can banner it — never fake stub
        # rows to hide a failure.
        raise HTTPException(status_code=502, detail=str(e)) from e
    search.page_token_current = ""
    search.page_token_next = next_token
    search.total_fetched = len(items)
    search.updated_at = datetime.utcnow()
    project.subject = query
    project.updated_at = datetime.utcnow()
    session.add(search)
    session.add(project)
    session.commit()

    saved = _persist_batch(session, search, items)
    # Downloads happen on-demand when the user clicks Download on a row, not
    # automatically for every candidate.

    return SearchBatchOut(
        search_id=search.id,
        project_id=project.id,
        provider=search.provider,
        query=search.query,
        has_more=bool(next_token),
        batch=[_as_video_out(v) for v in saved],
    )


@router.post("/{project_id}/search/next", response_model=SearchBatchOut)
def next_batch(
    project_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    project = _assert_project_access(session, project_id, user)
    search = session.exec(
        select(Search)
        .where(Search.project_id == project_id)
        .order_by(Search.updated_at.desc())
    ).first()
    if not search:
        raise HTTPException(status_code=400, detail="Start a search first")
    if not search.page_token_next:
        raise HTTPException(status_code=400, detail="No more pages from this provider")

    # Purge unkept candidates from the previous batch first (files + rows).
    _purge_non_kept(session, search)
    adapter = _provider_for(search.provider)
    try:
        items, next_token = adapter.search(search.query, search.page_token_next)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    search.page_token_current = search.page_token_next
    search.page_token_next = next_token
    search.total_fetched += len(items)
    search.updated_at = datetime.utcnow()
    project.updated_at = datetime.utcnow()
    session.add(search)
    session.add(project)
    session.commit()

    saved = _persist_batch(session, search, items)
    # Downloads happen on-demand when the user clicks Download on a row.

    return SearchBatchOut(
        search_id=search.id,
        project_id=project.id,
        provider=search.provider,
        query=search.query,
        has_more=bool(next_token),
        batch=[_as_video_out(v) for v in saved],
    )


@router.get("/{project_id}/kept", response_model=list[VideoOut])
def list_kept(
    project_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    _assert_project_access(session, project_id, user)
    rows = session.exec(
        select(Video)
        .where(Video.project_id == project_id, Video.state == "keep")
        .order_by(Video.decided_at.desc())
    ).all()
    return [_as_video_out(v) for v in rows]
