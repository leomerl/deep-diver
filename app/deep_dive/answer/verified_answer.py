from pydantic import BaseModel, Field

from .correction import Correction
from .deep_dive_answer import DeepDiveAnswer


class VerifiedAnswer(BaseModel):
    """Submit the checked write-up: every correction you made, then the full answer with those corrections applied
    and everything else unchanged. Call this once."""
    corrections: list[Correction] = Field(description="Empty if every claim held up.")
    answer: DeepDiveAnswer
