from __future__ import annotations
from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str
    role: str = "user"  # admin | user | readonly
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    subject: str = ""  # last searched subject
    owner_id: int = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Search(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(index=True)
    provider: str  # youtube | facebook
    query: str
    page_token_current: str = ""
    page_token_next: str = ""
    total_fetched: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Video(SQLModel, table=True):
    """One candidate per row. `state` governs the keep/reject flow and whether
    the file on disk should persist when the next page is requested."""

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(index=True)
    search_id: int = Field(index=True)
    provider: str  # youtube | facebook
    provider_video_id: str = Field(index=True)
    title: str = ""
    channel: str = ""
    description: str = ""
    duration_sec: float = 0.0
    view_count: int = 0
    published_at: str = ""
    thumbnail_url: str = ""
    source_url: str = ""  # canonical watch URL
    file_path: str = ""  # populated once downloaded
    state: str = "candidate"  # candidate | keep | rejected | purged
    created_at: datetime = Field(default_factory=datetime.utcnow)
    decided_at: Optional[datetime] = None


class AppConfig(SQLModel, table=True):
    """Key-value table for YouTube key, Facebook cookies, etc. Secrets are
    stored encrypted-at-rest when CONFIG_MASTER_KEY is provisioned (future
    work); for now values are plaintext but guarded by the admin auth gate
    and never returned to the frontend."""

    __tablename__ = "app_config"
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True, max_length=128)
    value: str = ""
    updated_at: datetime = Field(default_factory=datetime.utcnow)
