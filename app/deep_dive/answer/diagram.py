from typing import Literal, Self

from pydantic import BaseModel, Field, PrivateAttr, ValidationInfo, model_validator

from app.kroki import DiagramLanguage, DiagramSyntaxError

from .answer_context import AnswerContext
from .prose import Prose


class Diagram(BaseModel):
    """A diagram written as text. It is rendered to SVG when you submit, so a syntax error rejects the answer."""
    type: Literal["diagram"]
    language: DiagramLanguage = Field(
        description="mermaid for sequence, state and ER diagrams; graphviz for dependency or structure graphs with "
        "many nodes."
    )
    source: str = Field(description="The diagram source, e.g. `sequenceDiagram ...` or `digraph { ... }`.")
    caption: Prose = Field(description="One sentence saying what the diagram shows. It doubles as the alt text.")
    # Filled by the validator, kept out of the schema: the model writes the source, never the SVG.
    _svg: str = PrivateAttr()

    @property
    def svg(self) -> str:
        return self._svg

    @model_validator(mode="after")
    def _renders(self, info: ValidationInfo) -> Self:
        if not isinstance(info.context, AnswerContext):
            raise TypeError("Diagram is validated with an AnswerContext as context")
        try:
            self._svg = info.context.render_diagram(self.language, self.source)
        except DiagramSyntaxError as e:
            # Only syntax errors become a rejection the agent can fix; a renderer outage propagates and fails the job.
            raise ValueError(f"{self.language} rejected the diagram: {e}") from e
        return self
