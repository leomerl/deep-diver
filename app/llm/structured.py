from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

_METHOD = "json_schema"

def structured_call[T: BaseModel](chat_model: BaseChatModel, schema: type[T], system: str, user: str) -> T:
    """Ask the model and return its answer parsed as `schema`. Raises if the output doesn't parse."""
    result = chat_model.with_structured_output(schema, method=_METHOD).invoke(
        [SystemMessage(system), HumanMessage(user)]
    )
    if not isinstance(result, schema):
        raise TypeError(f"expected {schema.__name__}, got {type(result).__name__}")
    return result