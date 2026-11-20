from pydantic import BaseModel

from .json_object import JsonObject


class ResponseSchema(BaseModel):
    """Set on a request when the final answer must be JSON matching this schema (native structured output)."""
    name: str
    json_schema: JsonObject  # not `schema`: BaseModel already has an attribute with that name
