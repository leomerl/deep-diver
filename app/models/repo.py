from datetime import UTC, datetime
from enum import StrEnum

import sqlalchemy as sa
from pydantic import field_validator
from sqlmodel import Field, SQLModel

from app.repo_url import normalize_repo_url


def _now() -> datetime:
    return datetime.now(UTC)


class RepoStatus(StrEnum):
    indexing = "indexing"
    indexed = "indexed"
    failed = "failed"


class RepoBase(SQLModel):
    url: str = Field(unique=True, max_length=2048)  # one URL = one repo


class RepoCreate(RepoBase):
    """POST /repos body, and the index job payload (the worker re-validates with the same class)."""

    @field_validator("url")
    @classmethod
    def _normalize(cls, url: str) -> str:
        return normalize_repo_url(url)


class Repo(RepoBase, table=True):
    __tablename__ = "repos"

    id: int | None = Field(default=None, primary_key=True)
    commit_sha: str | None = Field(default=None, max_length=40)  # pinned at index time
    # native_enum=False: stored as VARCHAR, so adding a status later needs no ALTER TYPE
    # index serves GET /repos (indexed only)
    status: RepoStatus = Field(
        default=RepoStatus.indexing, sa_type=sa.Enum(RepoStatus, native_enum=False, length=16), index=True
    )
    # Whose GitHub token clones this repo (deep dives clone again, long after indexing). NULL: added anonymously.
    added_by: int | None = Field(default=None, foreign_key="users.id", ondelete="SET NULL")
    created_at: datetime = Field(default_factory=_now, sa_type=sa.DateTime(timezone=True))
    updated_at: datetime = Field(
        default_factory=_now, sa_type=sa.DateTime(timezone=True), sa_column_kwargs={"onupdate": _now}
    )


class RepoRead(RepoBase):
    id: int
    commit_sha: str | None
    status: RepoStatus
    added_by: int | None
    created_at: datetime
