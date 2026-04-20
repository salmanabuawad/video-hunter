from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class LoginIn(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str


class ProjectCreate(BaseModel):
    name: str


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    subject: str = ""
    owner_id: int
    created_at: datetime
    updated_at: datetime


class SearchStartIn(BaseModel):
    subject: str
    provider: str = "youtube"  # youtube | facebook


class VideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    search_id: int
    provider: str
    provider_video_id: str
    title: str
    channel: str
    description: str
    duration_sec: float
    view_count: int
    published_at: str
    thumbnail_url: str
    source_url: str
    state: str
    has_local_file: bool = False
    download_url: Optional[str] = None
    created_at: datetime


class DecideIn(BaseModel):
    decision: str  # keep | reject


class SearchBatchOut(BaseModel):
    search_id: int
    project_id: int
    provider: str
    query: str
    has_more: bool
    batch: list[VideoOut]


class AppConfigIn(BaseModel):
    youtube_api_key: Optional[str] = None
    facebook_cookies: Optional[str] = None


class AppConfigStatus(BaseModel):
    youtube_configured: bool
    facebook_configured: bool
