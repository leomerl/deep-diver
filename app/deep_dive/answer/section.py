from pydantic import BaseModel, Field, field_validator

from app.deep_dive.generic_headings import GENERIC_HEADINGS

from .block import Block
from .prose import Prose


class Section(BaseModel):
    heading: Prose = Field(description="Sentence case, contains a term from this area, names what the section holds.")
    blocks: list[Block] = Field(min_length=1)

    @field_validator("heading")
    @classmethod
    def _specific(cls, heading: str) -> str:
        if heading.strip().casefold() in GENERIC_HEADINGS:
            raise ValueError(f"{heading!r} is a generic heading; name what this section says about this area")
        return heading
