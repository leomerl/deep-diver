from datetime import UTC, datetime

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class SnapshotBase(SQLModel):
    repo_id: int = Field(foreign_key="repos.id", ondelete="CASCADE")
    commit_sha: str = Field(max_length=40)


class Snapshot(SnapshotBase, table=True):
    """One indexed commit of a repo. Its tree is written in one transaction and never edited; a re-index adds a new
    snapshot instead, so deep dives keep the commit they were written from."""

    __tablename__ = "snapshots"
    # One tree per commit: the fence for redelivered and zombie index jobs, and the worker's "already built?" lookup.
    __table_args__ = (sa.UniqueConstraint("repo_id", "commit_sha", name="uq_snapshots_repo_commit"),)

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), sa_type=sa.DateTime(timezone=True))
