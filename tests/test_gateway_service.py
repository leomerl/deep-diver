from collections.abc import Iterator
from types import SimpleNamespace

import anthropic
import httpx
import httpx2
import pytest
from anthropic.types.beta import BetaMessage
from fastapi import status
from fastapi.testclient import TestClient

from app.gateway import main
from app.llm.gateway_contract import ChatRequest, Message, ResponseSchema, Role, ToolCall, ToolSpec

REPLY = BetaMessage.model_validate({
    "id": "msg_1", "type": "message", "role": "assistant", "model": "m", "stop_sequence": None,
    "content": [
        {"type": "thinking", "thinking": "", "signature": "sig"},
        {"type": "text", "text": "Looking."},
        {"type": "tool_use", "id": "t3", "name": "tree", "input": {"path": "app"}},
    ],
    "stop_reason": "tool_use",
    "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 0},
})
REQUEST = ChatRequest(
    model="claude-opus-5-5",
    max_tokens=1000,
    messages=[
        Message(role=Role.system, content="You map repos."),
        Message(role=Role.user, content="Split it."),
        Message(role=Role.assistant, tool_calls=[
            ToolCall(id="t1", name="tree", arguments={}), ToolCall(id="t2", name="grep", arguments={"pattern": "x"}),
        ]),
        Message(role=Role.tool, content="app/", tool_call_id="t1"),
        Message(role=Role.tool, content="no matches", tool_call_id="t2"),
    ],
    tools=[ToolSpec(name="tree", description="Show the tree.", parameters={"type": "object", "properties": {}})],
)


class FakeAnthropic:
    """Stands in for anthropic.Anthropic: records create() kwargs, returns a reply or raises."""

    def __init__(self, reply: BetaMessage | Exception) -> None:
        self.reply = reply
        self.calls: list[dict[str, object]] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: object) -> BetaMessage:
        self.calls.append(kwargs)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


@pytest.fixture
def fake() -> Iterator[FakeAnthropic]:
    client = FakeAnthropic(REPLY)
    main.app.dependency_overrides[main.get_client] = lambda: client
    yield client
    main.app.dependency_overrides.clear()


def _post(request: ChatRequest = REQUEST, headers: dict[str, str] | None = None) -> httpx.Response:
    return TestClient(main.app).post("/v1/chat", json=request.model_dump(mode="json"), headers=headers or {})


def test_translates_request_and_reply(fake: FakeAnthropic) -> None:
    response = _post()

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "message": {
            "role": "assistant", "content": "Looking.", "tool_call_id": None,
            "tool_calls": [{"id": "t3", "name": "tree", "arguments": {"path": "app"}}],
        },
        "stop_reason": "tool_use",
        "usage": {  # cached input still counts as input; the cache fields split it out for cost
            "input_tokens": 110, "output_tokens": 5, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 0,
        },
    }
    [sent] = fake.calls
    assert sent["system"] == "You map repos."
    assert sent["tools"] == [{"name": "tree", "description": "Show the tree.", "input_schema": {"type": "object", "properties": {}}}]
    *_, results = sent["messages"]  # type: ignore[misc]  # kwargs are untyped in the fake
    # Both results of one assistant turn go back in a single user message.
    assert results == {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "t1", "content": "app/"},
        {"type": "tool_result", "tool_use_id": "t2", "content": "no matches"},
    ]}
    assert sent["betas"] == [main.FALLBACK_BETA]


def test_response_schema_becomes_structured_output(fake: FakeAnthropic) -> None:
    schema = {"type": "object", "properties": {"name": {"type": "string", "minLength": 1}}, "required": ["name"]}
    _post(REQUEST.model_copy(update={"response_schema": ResponseSchema(name="Area", json_schema=schema)}))

    sent_format = fake.calls[0]["output_config"]["format"]  # type: ignore[index]  # kwargs are untyped in the fake
    assert sent_format["type"] == "json_schema"
    assert sent_format["schema"]["additionalProperties"] is False


@pytest.mark.parametrize(("error", "code"), [
    (anthropic.RateLimitError, status.HTTP_429_TOO_MANY_REQUESTS),
    (anthropic.BadRequestError, status.HTTP_400_BAD_REQUEST),
    (anthropic.InternalServerError, status.HTTP_502_BAD_GATEWAY),
])
def test_provider_errors_map_to_retryable_or_not(fake: FakeAnthropic, error: type[anthropic.APIStatusError], code: int) -> None:
    response = httpx2.Response(code, request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"))
    fake.reply = error("provider said no", response=response, body=None)

    assert _post().status_code == code


def test_gateway_key_is_required_when_set(fake: FakeAnthropic, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "GATEWAY_KEY", "s3cret")

    assert _post().status_code == status.HTTP_401_UNAUTHORIZED
    assert _post(headers={"Authorization": "Bearer s3cret"}).status_code == status.HTTP_200_OK
