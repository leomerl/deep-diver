from typing import Self

from pydantic import model_validator

from app.models import InterviewQuestionBase

from .prose import check_prose


class InterviewQuestionDraft(InterviewQuestionBase):
    """A question an interviewer would ask about this code, and the answer a strong candidate would give."""

    @model_validator(mode="after")
    def _humanized(self) -> Self:
        # Reuses the table's shape instead of redeclaring the fields as `Prose`, so the check runs here.
        # One call over both fields lists every hit at once: the agent gets a single retry.
        check_prose(f"{self.question} {self.answer}")
        return self
