from sqlmodel import Field, SQLModel


class InterviewQuestionBase(SQLModel):
    question: str
    answer: str


class InterviewQuestion(InterviewQuestionBase, table=True):
    """A question an interviewer would ask about one area, with a model answer: the self-quiz bank."""
    __tablename__ = "interview_questions"

    id: int | None = Field(default=None, primary_key=True)
    # index serves "the questions of one deep dive" (quiz per node)
    deep_dive_id: int = Field(foreign_key="deep_dives.id", ondelete="CASCADE", index=True)


class InterviewQuestionRead(InterviewQuestionBase):
    id: int
    deep_dive_id: int
