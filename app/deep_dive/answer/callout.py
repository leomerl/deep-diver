from typing import Literal

from pydantic import BaseModel

from .callout_kind import CalloutKind
from .prose import Prose


class Callout(BaseModel):
    """A boxed aside, one short paragraph."""
    type: Literal["callout"]
    kind: CalloutKind
    text: Prose
