import uuid

from pydantic import BaseModel


class Caller(BaseModel):
    """Who asked for a call, so the gateway's usage rows can be grouped by agent run."""

    label: str  # no length cap: a long breadcrumb must not fail an agent run over bookkeeping
    run_id: uuid.UUID  # one per agent run
