from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool

from app.llm.gateway_contract import ToolSpec

# LangChain's own type for what bind_tools accepts; Any comes from its signature.
ToolLike = dict[str, Any] | type | Callable[..., Any] | BaseTool


def to_tool_specs(tools: Sequence[ToolLike]) -> list[ToolSpec]:
    """LangChain tools, Pydantic models or functions -> gateway tool definitions.

    A tool without a description fails validation here: the model chooses tools by their descriptions.
    """
    return [ToolSpec.model_validate(convert_to_openai_tool(tool)["function"]) for tool in tools]
