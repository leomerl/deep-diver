from typing import Literal, Self

from langchain_core.tools import ToolException
from pydantic import BaseModel, Field, ValidationInfo, model_validator

from .answer_context import AnswerContext
from .prose import Prose

MAX_EXCERPT_LINES = 25  # reviews found every longer excerpt spanned two functions


class CodeExcerpt(BaseModel):
    """A pointer to real lines in the repo. The renderer copies the lines, so the model can't invent code."""
    type: Literal["code"]
    path: str = Field(description="File relative to the repo root.")
    start_line: int = Field(ge=1, description="First line, 1-based.")
    end_line: int = Field(description="Last line, inclusive.")
    caption: Prose

    @model_validator(mode="after")
    def _real_lines(self, info: ValidationInfo) -> Self:
        if self.end_line < self.start_line:
            raise ValueError(f"end_line {self.end_line} is before start_line {self.start_line}")
        if self.end_line - self.start_line + 1 > MAX_EXCERPT_LINES:
            raise ValueError(f"excerpt is longer than {MAX_EXCERPT_LINES} lines; pick the lines that matter")
        if not isinstance(info.context, AnswerContext):
            raise TypeError("CodeExcerpt is validated with an AnswerContext as context")
        workspace = info.context.workspace
        try:
            lines = len(workspace.file_path(self.path).read_text(encoding="utf-8", errors="replace").splitlines())
        except ToolException as e:
            raise ValueError(str(e)) from e
        if self.end_line > lines:
            raise ValueError(f"{self.path} has {lines} lines, end_line {self.end_line} is past the end")
        return self
