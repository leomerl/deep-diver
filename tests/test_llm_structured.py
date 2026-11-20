import os

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import BaseModel

from app.config import LLM_GATEWAY_URL, LLM_MAX_TOKENS, LLM_MODEL, LLM_TIMEOUT_S
from app.llm import structured_call
from app.llm.gateway_chat_model import GatewayChatModel


class Area(BaseModel):
    name: str
    description: str


class FakeChat(BaseChatModel):
    """Returns a canned answer and remembers which structured-output method it was asked for."""

    canned: BaseModel | dict[str, str]
    method: str = ""

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _generate(self, messages: list[BaseMessage], stop: list[str] | None = None, **kwargs: object) -> ChatResult:
        raise NotImplementedError

    def with_structured_output(self, schema: object, *, method: str = "", **kwargs: object) -> Runnable:
        self.method = method
        return RunnableLambda(lambda _: self.canned)


def test_returns_parsed_schema_with_native_method() -> None:
    fake = FakeChat(canned=Area(name="API", description="HTTP routes"))

    assert structured_call(fake, Area, "sys", "user") == Area(name="API", description="HTTP routes")
    assert fake.method == "json_schema"


def test_wrong_type_raises() -> None:
    fake = FakeChat(canned={"name": "API", "description": "HTTP routes"})

    with pytest.raises(TypeError):
        structured_call(fake, Area, "sys", "user")


@pytest.mark.skipif(not os.getenv("LLM_GATEWAY_URL"), reason="needs LLM_GATEWAY_URL; calls the real gateway")
def test_live_gateway() -> None:
    chat = GatewayChatModel(
        base_url=LLM_GATEWAY_URL, model=LLM_MODEL, max_tokens=LLM_MAX_TOKENS, timeout_s=LLM_TIMEOUT_S
    )

    area = structured_call(chat, Area, "Name a code area.", "Files: app/api/routes/repos.py, app/api/main.py")

    assert area.name
