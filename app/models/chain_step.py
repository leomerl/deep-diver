from sqlmodel import SQLModel

from .step_status import StepStatus


class ChainStep(SQLModel):
    """One link of a job's chain on the jobs page: a checkpointed step, or a job the job queued."""

    name: str
    status: StepStatus
