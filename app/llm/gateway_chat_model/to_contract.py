from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.messages import ToolCall as LangChainToolCall

from app.llm.gateway_contract import Message, Role, ToolCall


def to_contract(message: BaseMessage) -> Message:
    """One LangChain message -> one gateway message. Raises on a type the gateway can't carry."""
    match message:
        case SystemMessage():
            return Message(role=Role.system, content=message.text)
        case HumanMessage():
            return Message(role=Role.user, content=message.text)
        case AIMessage():
            return Message(
                role=Role.assistant,
                content=message.text,
                tool_calls=[_tool_call(call) for call in message.tool_calls],
            )
        case ToolMessage():
            return Message(role=Role.tool, content=message.text, tool_call_id=message.tool_call_id)
        case _:
            raise TypeError(f"the gateway can't carry a {type(message).__name__}")


def _tool_call(call: LangChainToolCall) -> ToolCall:
    if call["id"] is None:
        raise ValueError(f"tool call {call['name']!r} has no id")
    return ToolCall(id=call["id"], name=call["name"], arguments=call["args"])
