import asyncio
from collections.abc import Sequence
from typing import Any
from uuid import uuid4

from claude_agent_sdk import SdkMcpTool
from langchain_core.messages import ToolCall, ToolMessage
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool

ERROR_STATUS = "error"
TEXT = "text"


def to_sdk_tools(tools: Sequence[BaseTool]) -> list[SdkMcpTool[Any]]:
    """LangChain tools -> in-process MCP tools for the Agent SDK. Any comes from the SDK's handler signature."""
    return [_to_sdk_tool(tool) for tool in tools]


def _to_sdk_tool(tool: BaseTool) -> SdkMcpTool[Any]:
    spec = convert_to_openai_tool(tool)["function"]

    async def handler(args: dict[str, Any]) -> dict[str, Any]:
        # Invoked with a whole call, a LangChain tool returns a ToolMessage whose status says whether it failed
        # (bad arguments, ToolException). The id only pairs the message with the call; the SDK never sees it.
        call = ToolCall(name=tool.name, args=args, id=str(uuid4()), type="tool_call")
        # Workspace tools do blocking file IO, and the SDK runs handlers on its event loop.
        message = await asyncio.to_thread(tool.invoke, call)
        if not isinstance(message, ToolMessage):
            raise TypeError(f"tool {tool.name} returned {type(message).__name__}, not a ToolMessage")
        return {"content": [{"type": TEXT, "text": message.text}], "is_error": message.status == ERROR_STATUS}

    return SdkMcpTool(name=spec["name"], description=spec["description"], input_schema=spec["parameters"], handler=handler)
