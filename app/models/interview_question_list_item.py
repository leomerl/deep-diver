from .interview_question import InterviewQuestionRead


class InterviewQuestionListItem(InterviewQuestionRead):
    """GET /interview-questions item: the question plus the area it is about, for the practice page."""

    repo_id: int
    node_id: int | None  # None: from the whole-repo deep dive
    node_name: str | None
    repo_url: str
