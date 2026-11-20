from collections.abc import Callable

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import ValidationError


def make_tool(func: Callable[..., str]) -> BaseTool:
    """A LangChain tool from a typed function. Its docstring and argument descriptions are what the model reads.

    Bad arguments and ToolExceptions go back to the model as the tool's result, so it can correct itself.
    Any other exception is a bug and propagates.
    """
    return StructuredTool.from_function(func, handle_tool_error=True, handle_validation_error=_explain)


def _explain(error: ValidationError) -> str:
    # LangChain's default text is just "Tool input validation error", which gives the model nothing to fix.
    return f"invalid arguments: {error}"
