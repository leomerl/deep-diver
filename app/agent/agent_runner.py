from collections.abc import Sequence
from typing import Protocol

from langchain_core.tools import BaseTool
from pydantic import BaseModel


class AgentRunner(Protocol):
    """What every agent runtime offers: let the model use `tools` until it answers in `answer`'s shape.

    The answer is validated with `answer.model_validate(..., context=context)`; a rejected answer goes back to
    the model. Raises AgentFailed when no valid answer comes within the turn budget.
    """

    def __call__[T: BaseModel](
        self,
        system: str,
        task: str,
        tools: Sequence[BaseTool],
        answer: type[T],
        max_turns: int,
        wrap_up_turns: int,
        label: str,
        context: object | None = None,
    ) -> T: ...
