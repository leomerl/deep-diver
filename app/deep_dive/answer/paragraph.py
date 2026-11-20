from typing import Literal

from pydantic import BaseModel

from .prose import Prose


class Paragraph(BaseModel):
    type: Literal["paragraph"]
    text: Prose
