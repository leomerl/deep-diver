from typing import Annotated

from pydantic import Field

from .callout import Callout
from .code_excerpt import CodeExcerpt
from .diagram import Diagram
from .paragraph import Paragraph
from .svg_figure import SvgFigure

Block = Annotated[Paragraph | Callout | CodeExcerpt | Diagram | SvgFigure, Field(discriminator="type")]
