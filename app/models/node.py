import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, SQLModel

from .grouping import Grouping


class NodeBase(SQLModel):
    """An area of the code. Every link to another node, the tree included, is an edge row."""

    name: str
    description: str | None = None
    # Files or folder prefixes that make up the area; a deep dive sparse-clones exactly these. Overlap is allowed.
    paths: list[str] = Field(sa_type=ARRAY(sa.String))
    # native_enum=False: stored as VARCHAR, so adding a value later needs no ALTER TYPE
    grouping: Grouping = Field(default=Grouping.llm, sa_type=sa.Enum(Grouping, native_enum=False, length=16))


class Node(NodeBase, table=True):
    __tablename__ = "nodes"
    # An area without paths would give a deep dive nothing to check out.
    __table_args__ = (sa.CheckConstraint("cardinality(paths) > 0", name="ck_nodes_has_paths"),)

    id: int | None = Field(default=None, primary_key=True)
    repo_id: int = Field(foreign_key="repos.id", ondelete="CASCADE", index=True)  # GET /repos/{id}/map


class NodeRead(NodeBase):
    id: int
