from datetime import UTC, datetime

import sqlalchemy as sa
from sqlmodel import Field, SQLModel

from app.queue import JobEventKind


class JobEventBase(SQLModel):
    """One thing that happened to a queued job. The job itself lives in Redis, which keeps only its current state;
    these rows are its history: each delivery, each checkpointed step, and why a delivery failed."""

    stream: str = Field(max_length=64)  # the job's stream: jobs:index or jobs:deep_dive
    entry_id: str = Field(max_length=32)  # the Redis entry id, which is the job's id
    kind: JobEventKind = Field(sa_type=sa.Enum(JobEventKind, native_enum=False, length=32))
    delivery: int  # 1 is the first try
    consumer: str = Field(max_length=128)  # the worker process (host-pid)
    detail: str | None = Field(default=None, sa_type=sa.Text)  # the step for `step`, the exception for `failed`


class JobEvent(JobEventBase, table=True):
    __tablename__ = "job_events"
    # serves GET /jobs: the events of the listed jobs, in order
    __table_args__ = (sa.Index("ix_job_events_job", "stream", "entry_id"),)

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), sa_type=sa.DateTime(timezone=True))


class JobEventRead(JobEventBase):
    id: int
    created_at: datetime
