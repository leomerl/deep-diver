from typing import Self

from pydantic import Field, model_validator

from app.models import NotebookBase

from .notebook_cell import NotebookCell
from .prose import check_prose

MIN_CELLS = 2
MAX_CELLS = 8  # a notebook a reader finishes in one sitting; the deep dive page carries the rest


class NotebookAnswer(NotebookBase):
    """Submit the runnable notebook for this code area. Call this once, after you have read the code it rebuilds."""
    # Narrowed from the stored shape to the cell that validates, with the bounds the agent must meet.
    cells: list[NotebookCell] = Field(  # type: ignore[assignment]  # a list of a subclass; pydantic re-validates it
        min_length=MIN_CELLS,
        max_length=MAX_CELLS,
        description="Small self-contained programs that rebuild this area's key mechanisms, in reading order. "
        "Later cells may use names defined by earlier ones.",
    )

    @model_validator(mode="after")
    def _humanized(self) -> Self:
        check_prose(self.title)
        return self
