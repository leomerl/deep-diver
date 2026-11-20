from typing import Self

from pydantic import BaseModel, model_validator

from .role import Role
from .tool_call import ToolCall


class Message(BaseModel):
    role: Role
    content: str = ""
    tool_calls: list[ToolCall] = []
    tool_call_id: str | None = None

    @model_validator(mode="after")
    def _fields_match_role(self) -> Self:
        if self.tool_calls and self.role != Role.assistant:
            raise ValueError("only assistant messages carry tool_calls")
        if (self.tool_call_id is not None) != (self.role == Role.tool):
            raise ValueError("tool messages, and only tool messages, carry tool_call_id")
        return self
