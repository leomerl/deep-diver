from datetime import datetime

from sqlmodel import SQLModel

from app.queue import JobState

from .chain_step import ChainStep
from .job_event import JobEventRead


class JobRead(SQLModel):
    """A queued job: its state from Redis, its history from job_events."""

    stream: str
    entry_id: str
    label: str  # what the job is about: a repo URL, or a deep dive's repo and node
    state: JobState
    queued_at: datetime  # the entry id's milliseconds
    deliveries: int  # tries so far; 0 while queued
    consumer: str | None  # the worker holding it, while pending
    chain: list[ChainStep]  # its checkpointed steps, then the jobs it queues; empty for a single-step job
    events: list[JobEventRead]  # oldest first
    follow_up: "JobRead | None" = None  # the job it queued when it finished: a deep dive's notebook
