import sqlalchemy as sa
from sqlmodel import Field, SQLModel

from .edge_kind import EdgeKind


class EdgeBase(SQLModel):
    """A directed link between two nodes. kind=contains is the tree; other kinds will be cross-links."""

    source_id: int = Field(foreign_key="nodes.id", ondelete="CASCADE")
    target_id: int = Field(foreign_key="nodes.id", ondelete="CASCADE", index=True)  # reverse lookups
    # native_enum=False: stored as VARCHAR, so adding a kind later needs no ALTER TYPE
    kind: EdgeKind = Field(sa_type=sa.Enum(EdgeKind, native_enum=False, length=16))
    label: str | None = None


class Edge(EdgeBase, table=True):
    __tablename__ = "edges"
    __table_args__ = (
        # One edge per pair. Its leftmost column also serves "children of X" (GET /nodes/{id}) and GET /repos/{id}/map.
        sa.UniqueConstraint("source_id", "target_id"),
        sa.CheckConstraint("source_id <> target_id", name="ck_edges_no_self_loop"),
        # At most one parent per node. Not acyclicity: DESIGN §4 explains why cycles can't happen in v1.
        sa.Index(
            "ux_edges_one_parent", "target_id", unique=True,
            postgresql_where=sa.text(f"kind = '{EdgeKind.contains.value}'"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)


class EdgeRead(EdgeBase):
    id: int
