import json

import httpx
import pytest
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.llm.gateway_chat_model import GatewayAnswerError, GatewayChatModel
from app.llm.gateway_contract import ChatRequest

BASE_URL = "http://gateway.test"


class Recorder:
    """Fake gateway: records each request and answers with a fixed response body."""

    def __init__(self, body: dict[str, object], status: int = 200) -> None:
        self.body, self.status = body, status
        self.requests: list[ChatRequest] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        assert request.url == f"{BASE_URL}/v1/chat"
        self.requests.append(ChatRequest.model_validate_json(request.content))
        return httpx.Response(self.status, json=self.body)


def _model(gateway: Recorder) -> GatewayChatModel:
    return GatewayChatModel(
        base_url=BASE_URL, model="m", max_tokens=100, timeout_s=5,
        http_client=httpx.Client(transport=httpx.MockTransport(gateway)),
    )


def _answer(content: str = "", tool_calls: list[dict[str, object]] | None = None, stop: str = "end_turn") -> dict[str, object]:
    return {
        "message": {"role": "assistant", "content": content, "tool_calls": tool_calls or []},
        "stop_reason": stop,
        "usage": {"input_tokens": 7, "output_tokens": 3},
    }


def tree(path: str = ".") -> str:
    """Show the folder tree."""
    return path


def test_tool_call_round_trip() -> None:
    gateway = Recorder(_answer(tool_calls=[{"id": "c1", "name": "tree", "arguments": {"path": "app"}}], stop="tool_use"))

    reply = _model(gateway).bind_tools([tree]).invoke([SystemMessage("map it"), HumanMessage("go")])

    [sent] = gateway.requests
    assert [m.role for m in sent.messages] == ["system", "user"]
    assert [t.name for t in sent.tools] == ["tree"]
    assert reply.tool_calls == [{"name": "tree", "args": {"path": "app"}, "id": "c1", "type": "tool_call"}]
    assert reply.usage_metadata == {
        "input_tokens": 7, "output_tokens": 3, "total_tokens": 10,
        "input_token_details": {"cache_read": 0, "cache_creation": 0},  # the gateway sent no cache fields: defaults
    }


def test_structured_output_sends_schema_and_parses_answer() -> None:
    class Verdict(BaseModel):
        ok: bool

    gateway = Recorder(_answer(content=json.dumps({"ok": True})))

    assert _model(gateway).with_structured_output(Verdict).invoke("is it ok?") == Verdict(ok=True)
    assert gateway.requests[0].response_schema is not None
    assert gateway.requests[0].response_schema.name == "Verdict"


@pytest.mark.parametrize("stop", ["max_tokens", "refusal"])
def test_unusable_answer_raises(stop: str) -> None:
    with pytest.raises(GatewayAnswerError):
        _model(Recorder(_answer(content="half an ans", stop=stop))).invoke("hi")


def test_http_error_is_not_a_gateway_answer_error() -> None:
    # An unreachable or failing gateway must fail the job, not trigger a per-node fallback.
    with pytest.raises(httpx.HTTPStatusError):
        _model(Recorder({}, status=503)).invoke("hi")


def test_unsupported_options_fail_loudly() -> None:
    model = _model(Recorder(_answer()))
    with pytest.raises(ValueError):
        model.bind_tools([tree], tool_choice="any")
    with pytest.raises(ValueError):
        model.invoke("hi", stop=["END"])
