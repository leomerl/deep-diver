from collections.abc import Callable
from dataclasses import dataclass

from app.kroki import DiagramLanguage
from app.workspace import Workspace

type RenderDiagram = Callable[[DiagramLanguage, str], str]  # (language, source) -> svg


@dataclass(frozen=True)
class AnswerContext:
    """What the answer is checked against: the checkout for code excerpts, the diagram renderer for diagrams."""
    workspace: Workspace
    render_diagram: RenderDiagram
