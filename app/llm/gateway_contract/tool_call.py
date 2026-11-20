from pydantic import BaseModel

from .json_object import JsonObject


class ToolCall(BaseModel):
    id: str  # the tool message echoes it, so each result pairs with its call
    name: str
    arguments: JsonObject  # each tool validates these with its own model; the contract only knows "JSON"
