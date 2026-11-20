import asyncio
from typing import Annotated, Any

from claude_agent_sdk import SdkMcpTool
from langchain_core.tools import ToolException
from pydantic import Field

from app.agent_sdk import to_sdk_tools
from app.workspace.make_tool import make_tool


def shout(text: Annotated[str, Field(description="What to shout.")], times: int = 1) -> str:
    """Shout the text."""
    if text == "boom":
        raise ToolException("no booms")
    return text.upper() * times


def _shout_tool() -> SdkMcpTool[Any]:  # Any: the SDK's own generic parameter
    [tool] = to_sdk_tools([make_tool(shout)])
    return tool


def test_name_description_and_schema_come_from_the_tool() -> None:
    tool = _shout_tool()
    assert tool.name == "shout"
    assert tool.description == "Shout the text."
    assert isinstance(tool.input_schema, dict)
    assert tool.input_schema["type"] == "object"
    assert tool.input_schema["properties"]["text"]["description"] == "What to shout."
    assert tool.input_schema["required"] == ["text"]


def test_handler_returns_the_tools_text() -> None:
    result = asyncio.run(_shout_tool().handler({"text": "hi", "times": 2}))
    assert result == {"content": [{"type": "text", "text": "HIHI"}], "is_error": False}


def test_bad_arguments_are_an_error_result_not_an_exception() -> None:
    result = asyncio.run(_shout_tool().handler({"text": 5}))
    assert result["is_error"] is True
    assert "invalid arguments" in result["content"][0]["text"]


def test_tool_exceptions_are_an_error_result() -> None:
    result = asyncio.run(_shout_tool().handler({"text": "boom"}))
    assert result["is_error"] is True
    assert "no booms" in result["content"][0]["text"]
