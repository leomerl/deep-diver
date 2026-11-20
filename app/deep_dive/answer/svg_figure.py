import xml.etree.ElementTree as ET
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from .prose import Prose

MAX_SVG_BYTES = 40_000  # a hand-drawn figure of a few dozen shapes; anything bigger is pasted art, not a figure
SVG_NS = "http://www.w3.org/2000/svg"
SVG_TAG = f"{{{SVG_NS}}}svg"
SCRIPT_TAG = f"{{{SVG_NS}}}script"


class SvgFigure(BaseModel):
    """A figure you draw yourself as SVG, for what no layout engine draws: a byte layout, a buffer, a timeline."""
    type: Literal["svg"]
    svg: str = Field(
        description=f'A complete <svg xmlns="{SVG_NS}"> document with a viewBox, under {MAX_SVG_BYTES} bytes, '
        "no <script>. Use text large enough to read when the figure is 40rem wide."
    )
    caption: Prose = Field(description="One sentence saying what the figure shows. It doubles as the alt text.")

    @model_validator(mode="after")
    def _well_formed(self) -> Self:
        if len(self.svg.encode()) > MAX_SVG_BYTES:
            raise ValueError(f"the SVG is over {MAX_SVG_BYTES} bytes; draw fewer shapes")
        try:
            root = ET.fromstring(self.svg)
        except ET.ParseError as e:
            raise ValueError(f"the SVG is not well-formed XML: {e}") from e
        if root.tag != SVG_TAG:
            raise ValueError(f'the root element must be <svg xmlns="{SVG_NS}">, got <{root.tag}>')
        if "viewBox" not in root.attrib:
            raise ValueError("the <svg> needs a viewBox, or it can't scale to the page width")
        # Shown through <img>, so a script would never run; rejecting it still keeps the stored page clean.
        if next(root.iter(SCRIPT_TAG), None) is not None:
            raise ValueError("no <script> in SVG figures")
        return self
