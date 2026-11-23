from datetime import UTC, datetime

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class DeepDiveBase(SQLModel):
    # Set on every row, the root's included: it pins the commit the page was written from, so a re-index leaves
    # the page valid for its own snapshot and merely not current.
    # TODO [DB:LOW] nothing in the database ties snapshot_id to the node's snapshot; a composite FK would.
    snapshot_id: int = Field(foreign_key="snapshots.id", ondelete="CASCADE")
    # NULL: the deep dive is about the whole repo. unique: one deep dive per node (a node belongs to one snapshot,
    # so it never goes stale); serves GET /nodes/{id}/deep-dive and the worker's "already done?" check. Postgres
    # treats NULLs as distinct, so this doesn't limit root deep dives; the partial index below does.
    node_id: int | None = Field(default=None, foreign_key="nodes.id", ondelete="CASCADE", unique=True)

    @property
    def target_key(self) -> str:
        """Names the deep dive's target in Redis dedup keys and LangGraph thread ids."""
        return f"snapshot-{self.snapshot_id}" if self.node_id is None else str(self.node_id)


class DeepDiveCreate(DeepDiveBase):
    """The deep dive job payload; the worker re-validates it with the same class."""


class DeepDive(DeepDiveBase, table=True):
    __tablename__ = "deep_dives"
    # One root deep dive per snapshot. Serves GET /repos/{id}/deep-dive and the worker's check for a root job.
    __table_args__ = (
        sa.Index(
            "uq_deep_dives_snapshot_root", "snapshot_id", unique=True, postgresql_where=sa.text("node_id IS NULL")
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    # The HTML lives in the bucket under sha256(html).html; the row only points at it.
    object_key: str = Field(max_length=128)
    # The notebook's JSON, also content-addressed in the bucket. NULL: the notebook agent failed (the page still
    # ships) or the page predates notebooks.
    notebook_key: str | None = Field(default=None, max_length=128)
    # index serves GET /deep-dives (newest first)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), sa_type=sa.DateTime(timezone=True), index=True
    )


class DeepDiveRead(DeepDiveBase):
    id: int
    object_key: str
    notebook_key: str | None
    created_at: datetime
