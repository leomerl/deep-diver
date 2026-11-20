from typing import Self

from pydantic import BaseModel, Field, model_validator

from app.deep_dive.generic_headings import SUMMARY_PREFIXES

from .diagram import Diagram
from .interview_question_draft import InterviewQuestionDraft
from .prose import Prose
from .section import Section
from .svg_figure import SvgFigure
from .tech_choice import TechChoice

MIN_VISUALS = 1


class DeepDiveAnswer(BaseModel):
    """Submit the finished write-up of this code area. Call this once, after you have read the code you cite."""
    title: Prose
    sections: list[Section] = Field(
        min_length=1, description=f"At least {MIN_VISUALS} diagrams or SVG figures across the sections."
    )
    tech_stack: list[TechChoice] = Field(
        default_factory=list,
        description="Technologies this area depends on that are worth discussing in an interview. Empty if none.",
    )
    interview_questions: list[InterviewQuestionDraft] = Field(
        min_length=3,
        max_length=6,
        description="Questions an interviewer would ask about this code, each with a spoken-style answer of one or "
        "two short paragraphs separated by a blank line. Not repeated in `sections`.",
    )

    @model_validator(mode="after")
    def _summary_last(self) -> Self:
        early = [s.heading for s in self.sections[:-1] if s.heading.strip().casefold().startswith(SUMMARY_PREFIXES)]
        if early:
            raise ValueError(f"only the last section may be a summary; move or rename: {', '.join(map(repr, early))}")
        return self

    @model_validator(mode="after")
    def _enough_visuals(self) -> Self:
        # A floor for the whole page, not one per section: some sections (a design choice, a short concept) have
        # nothing honest to draw, and a per-section rule rejected otherwise good answers, costing the one retry.
        visuals = sum(isinstance(block, Diagram | SvgFigure) for section in self.sections for block in section.blocks)
        if visuals < MIN_VISUALS:
            raise ValueError(f"the write-up has no diagram or SVG figure; it needs at least {MIN_VISUALS}")
        return self
