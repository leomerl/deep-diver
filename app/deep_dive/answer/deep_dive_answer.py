from typing import Self

from pydantic import BaseModel, Field, model_validator

from app.deep_dive.generic_headings import SUMMARY_PREFIXES

from .callout import Callout
from .diagram import Diagram
from .interview_question_draft import InterviewQuestionDraft
from .paragraph import Paragraph
from .prose import Prose
from .section import Section
from .svg_figure import SvgFigure
from .tech_choice import TechChoice

MIN_VISUALS = 1
# Ceilings, so the page stays focused: before them, pages ran 9 to 11 sections and 1,600 to 2,100 words of prose.
MAX_SECTIONS = 5
MAX_PROSE_WORDS = 900  # paragraphs + callouts in the sections; excerpts, diagrams and the quiz don't count
MAX_CALLOUTS = 4
MAX_TECH = 3


class DeepDiveAnswer(BaseModel):
    """Submit the finished write-up of this code area. Call this once, after you have read the code you cite."""
    title: Prose
    sections: list[Section] = Field(
        min_length=1,
        max_length=MAX_SECTIONS,
        description=f"At least {MIN_VISUALS} diagram or SVG figure across the sections. At most {MAX_CALLOUTS} "
        f"callouts and {MAX_PROSE_WORDS} words of paragraph and callout text in all.",
    )
    tech_stack: list[TechChoice] = Field(
        default_factory=list,
        max_length=MAX_TECH,
        description="Technologies this area depends on that are worth discussing in an interview. Empty if none.",
    )
    interview_questions: list[InterviewQuestionDraft] = Field(
        min_length=3,
        max_length=5,
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

    @model_validator(mode="after")
    def _within_budget(self) -> Self:
        # Both overruns in one message, so the one retry can fix both.
        blocks = [block for section in self.sections for block in section.blocks]
        words = sum(len(block.text.split()) for block in blocks if isinstance(block, Paragraph | Callout))
        callouts = sum(isinstance(block, Callout) for block in blocks)
        problems = [
            *([f"{words} words of paragraph and callout text; cut to {MAX_PROSE_WORDS} or fewer by dropping the "
               "least important points, not by shortening every sentence"] if words > MAX_PROSE_WORDS else []),
            *([f"{callouts} callouts; keep the {MAX_CALLOUTS} that matter most"] if callouts > MAX_CALLOUTS else []),
        ]
        if problems:
            raise ValueError("the write-up is too long: " + "; ".join(problems))
        return self
