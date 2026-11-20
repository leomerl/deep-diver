import pytest
from langchain_core.messages import AIMessage, ChatMessage, HumanMessage, SystemMessage, ToolMessage

from app.llm.gateway_chat_model.to_contract import to_contract
from app.llm.gateway_contract import Message, Role, ToolCall


def test_each_message_type_maps_to_its_role() -> None:
    messages = [
        SystemMessage("be brief"),
        HumanMessage([{"type": "text", "text": "map "}, {"type": "text", "text": "this repo"}]),
        AIMessage("", tool_calls=[{"name": "tree", "args": {"path": "."}, "id": "c1"}]),
        ToolMessage("app/ 12 files", tool_call_id="c1"),
    ]

    assert [to_contract(m) for m in messages] == [
        Message(role=Role.system, content="be brief"),
        Message(role=Role.user, content="map this repo"),
        Message(role=Role.assistant, tool_calls=[ToolCall(id="c1", name="tree", arguments={"path": "."})]),
        Message(role=Role.tool, content="app/ 12 files", tool_call_id="c1"),
    ]


def test_unknown_message_type_is_rejected() -> None:
    with pytest.raises(TypeError):
        to_contract(ChatMessage("hi", role="critic"))


def test_tool_call_without_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="no id"):
        to_contract(AIMessage("", tool_calls=[{"name": "tree", "args": {}, "id": None}]))
