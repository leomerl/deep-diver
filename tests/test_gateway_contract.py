import pytest
from pydantic import ValidationError

from app.llm.gateway_contract import ChatResponse, Message, Role, StopReason


def test_response_with_tool_calls_parses() -> None:
    response = ChatResponse.model_validate({
        "message": {"role": "assistant", "tool_calls": [{"id": "c1", "name": "tree", "arguments": {"path": "."}}]},
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 10, "output_tokens": 5},
    })
    assert (response.stop_reason, response.message.tool_calls[0].arguments) == (StopReason.tool_use, {"path": "."})


@pytest.mark.parametrize("fields", [
    {"role": Role.tool, "content": "result without a call id"},
    {"role": Role.user, "tool_call_id": "c1"},
    {"role": Role.user, "tool_calls": [{"id": "c1", "name": "tree", "arguments": {}}]},
])
def test_fields_that_dont_match_the_role_are_rejected(fields: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Message.model_validate(fields)
