from pydantic import BaseModel

from .message import Message
from .stop_reason import StopReason
from .usage import Usage


class ChatResponse(BaseModel):
    message: Message
    stop_reason: StopReason
    usage: Usage
