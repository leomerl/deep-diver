"""Data model: one file per entity.

Pattern (no duplicated fields):
  XBase   shared fields, plain Pydantic model
  X       XBase + table=True -> the DB table; Alembic migrations are generated from these
  XRead   XBase + id/server fields -> API response schema
  XCreate XBase + input validation -> API request schema
Enums and composite schemas (TreeNode, NodeWithChildren, RepoMap) get their own files.

Importing this package registers every table on SQLModel.metadata (Alembic relies on it).
"""
from .chain_step import ChainStep
from .deep_dive import DeepDive, DeepDiveBase, DeepDiveCreate, DeepDiveRead
from .deep_dive_list_item import DeepDiveListItem
from .edge import Edge, EdgeBase, EdgeRead
from .edge_kind import EdgeKind
from .grouping import Grouping
from .index_job import IndexJob
from .interview_question import InterviewQuestion, InterviewQuestionBase, InterviewQuestionRead
from .interview_question_list_item import InterviewQuestionListItem
from .job_event import JobEvent, JobEventBase, JobEventRead
from .job_read import JobRead
from .llm_call import LlmCall, LlmCallBase
from .node import Node, NodeBase, NodeRead
from .node_with_children import NodeWithChildren
from .notebook import NotebookBase, NotebookCellBase
from .notebook_job import NotebookJob
from .repo import Repo, RepoBase, RepoCreate, RepoRead, RepoStatus
from .repo_map import RepoMap
from .snapshot import Snapshot, SnapshotBase
from .step_status import StepStatus
from .tree_node import TreeNode
from .user import User, UserBase, UserRead

__all__ = [
    "ChainStep", "DeepDive", "DeepDiveBase", "DeepDiveCreate", "DeepDiveListItem", "DeepDiveRead",
    "Edge", "EdgeBase", "EdgeKind", "EdgeRead",
    "InterviewQuestion", "InterviewQuestionBase", "InterviewQuestionListItem", "InterviewQuestionRead",
    "JobEvent", "JobEventBase", "JobEventRead", "JobRead",
    "LlmCall", "LlmCallBase",
    "Grouping", "IndexJob", "Node", "NodeBase", "NodeRead", "NodeWithChildren", "NotebookBase", "NotebookCellBase", "NotebookJob", "TreeNode",
    "Repo", "RepoBase", "RepoCreate", "RepoMap", "RepoRead", "RepoStatus", "Snapshot", "SnapshotBase", "StepStatus",
    "User", "UserBase", "UserRead",
]
