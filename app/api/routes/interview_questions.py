from fastapi import APIRouter
from sqlmodel import col, select

from app.db import SessionDep
from app.models import DeepDive, InterviewQuestion, InterviewQuestionListItem, InterviewQuestionRead, Node, Repo, Snapshot

router = APIRouter(prefix="/interview-questions", tags=["interview questions"])


@router.get("")
def list_interview_questions(session: SessionDep) -> list[InterviewQuestionListItem]:
    """The whole self-quiz bank; the client filters by repo and shuffles."""
    # TODO [API:LOW] unpaginated; add a repo filter server-side once the bank grows past a few thousand.
    rows = session.exec(
        select(InterviewQuestion, Snapshot.repo_id, DeepDive.node_id, Node.name, Repo.url)
        .join(DeepDive, col(InterviewQuestion.deep_dive_id) == col(DeepDive.id))
        .join(Snapshot, col(DeepDive.snapshot_id) == col(Snapshot.id))
        .join(Repo, col(Snapshot.repo_id) == col(Repo.id))
        .outerjoin(Node, col(DeepDive.node_id) == col(Node.id))  # outer: a root deep dive has no node
        .order_by(col(InterviewQuestion.id))
    ).all()
    return [
        InterviewQuestionListItem(
            **InterviewQuestionRead.model_validate(q).model_dump(),
            repo_id=repo_id, node_id=node_id, node_name=name, repo_url=url,
        )
        for q, repo_id, node_id, name, url in rows
    ]
