from pydantic import BaseModel, Field


class NotebookCellBase(BaseModel):
    explanation: str = Field(
        description="What this cell shows and what to notice in its output, in one or two short paragraphs. "
        "Shown above the code."
    )
    code: str = Field(min_length=1, description="Self-contained Python that runs in the reader's browser.")
    mirrors: str | None = Field(
        default=None,
        description="The repo file whose mechanism this cell rebuilds, relative to the repo root. "
        "Null for a cell that only sets up or sums up.",
    )


class NotebookBase(BaseModel):
    """A runnable notebook: the JSON stored in the bucket and the GET /deep-dives/{id}/notebook response.

    Plain fields only. The agent's NotebookAnswer adds the checks; reading a stored notebook must not re-run them,
    or tightening a rule would make every older notebook unreadable.
    """
    title: str
    cells: list[NotebookCellBase]
