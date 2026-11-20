from pydantic import BaseModel, Field

from .alternative import Alternative
from .prose import Prose


class TechChoice(BaseModel):
    """One library, service or tool this area depends on."""
    name: Prose = Field(description="e.g. Redis Streams, SQLModel, LangChain.")
    role: Prose = Field(description="What it does in this area, concretely.")
    pros: list[Prose] = Field(min_length=1, description="Why it fits here, one point each.")
    cons: list[Prose] = Field(min_length=1, description="What it costs or where it hurts here, one point each.")
    alternatives: list[Alternative] = Field(min_length=1)
    fit: Prose = Field(description="How it fits the system's overall design and the other parts of the stack.")
