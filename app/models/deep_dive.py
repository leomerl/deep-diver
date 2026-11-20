from datetime import UTC, datetime

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class DeepDiveBase(SQLModel):
    # unique: one deep dive per node (its commit is pinned, so it never goes stale). Also serves
    # GET /nodes/{id}/deep-dive and the worker's "already done?" check.
    node_id: int = Field(foreign_key="nodes.id", ondelete="CASCADE", unique=True)


class DeepDiveCreate(DeepDiveBase):
    """The deep dive job payload; the worker re-validates it with the same class."""


class DeepDive(DeepDiveBase, table=True):
    __tablename__ = "deep_dives"

    id: int | None = Field(default=None, primary_key=True)
    # The HTML lives in the bucket under sha256(html).html; the row only points at it.
    object_key: str = Field(max_length=128)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), sa_type=sa.DateTime(timezone=True))


class DeepDiveRead(DeepDiveBase):
    id: int
    object_key: str
    created_at: datetime
