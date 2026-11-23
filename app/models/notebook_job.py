from sqlmodel import SQLModel


class NotebookJob(SQLModel):
    """The notebook job payload; the worker re-validates it with the same class. The page must exist: the agent
    works from it."""

    deep_dive_id: int
