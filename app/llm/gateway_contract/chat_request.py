from pydantic import BaseModel

from .caller import Caller
from .message import Message
from .response_schema import ResponseSchema
from .tool_spec import ToolSpec


class ChatRequest(BaseModel):
    model: str
    messages: list[Message]
    tools: list[ToolSpec] = []
    response_schema: ResponseSchema | None = None
    max_tokens: int
    caller: Caller | None = None  # optional, so an older client still parses
