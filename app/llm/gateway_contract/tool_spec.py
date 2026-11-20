from pydantic import BaseModel

from .json_object import JsonObject


class ToolSpec(BaseModel):
    name: str
    description: str
    parameters: JsonObject  # JSON Schema of the arguments
