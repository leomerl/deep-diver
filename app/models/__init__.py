"""Data model: one file per entity.

Pattern (no duplicated fields):
  XBase   shared fields, plain Pydantic model
  X       XBase + table=True -> the DB table; Alembic migrations are generated from these
  XRead   XBase + id/server fields -> API response schema
  XCreate XBase + input validation -> API request schema
Enums and composite schemas (TreeNode, NodeWithChildren, RepoMap) get their own files.

Importing this package registers every table on SQLModel.metadata (Alembic relies on it).
"""
from .deep_dive import DeepDive, DeepDiveBase, DeepDiveCreate, DeepDiveRead
from .edge import Edge, EdgeBase, EdgeRead
from .edge_kind import EdgeKind
from .grouping import Grouping
from .index_job import IndexJob
from .interview_question import InterviewQuestion, InterviewQuestionBase, InterviewQuestionRead
from .node import Node, NodeBase, NodeRead
from .node_with_children import NodeWithChildren
from .repo import Repo, RepoBase, RepoCreate, RepoRead, RepoStatus
from .repo_map import RepoMap
from .tree_node import TreeNode
from .user import User, UserBase, UserRead

__all__ = [
    "DeepDive", "DeepDiveBase", "DeepDiveCreate", "DeepDiveRead",
    "Edge", "EdgeBase", "EdgeKind", "EdgeRead",
    "InterviewQuestion", "InterviewQuestionBase", "InterviewQuestionRead",
    "Grouping", "IndexJob", "Node", "NodeBase", "NodeRead", "NodeWithChildren", "TreeNode",
    "Repo", "RepoBase", "RepoCreate", "RepoMap", "RepoRead", "RepoStatus",
    "User", "UserBase", "UserRead",
]
