from collections.abc import Sequence
from typing import Any

import httpx
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import BaseModel, Field, SecretStr

from app.llm.gateway_contract import CHAT_PATH, Caller, ChatRequest, ChatResponse, ResponseSchema, ToolSpec

from .from_contract import from_contract
from .to_contract import to_contract
from .tool_specs import ToolLike, to_tool_specs

# The only structured-output method the gateway has: native JSON schema output.
JSON_SCHEMA_METHOD = "json_schema"


class GatewayChatModel(BaseChatModel):
    """A LangChain chat model backed by the in-house AI gateway, so LangGraph and our agent loop can use it.

    Any in the overridden signatures below comes from BaseChatModel's own signatures.
    """

    base_url: str
    model: str
    max_tokens: int
    timeout_s: float
    api_key: SecretStr | None = None
    caller: Caller | None = None  # sent with every call; set per agent run with model_copy
    # One pooled client per model instance; tests inject one with a mock transport.
    http_client: httpx.Client = Field(default_factory=httpx.Client, exclude=True)

    @property
    def _llm_type(self) -> str:
        return "deep-diver-gateway"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        *,
        tools: list[ToolSpec] | None = None,
        response_schema: ResponseSchema | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        # Silently ignoring an option would change behaviour without anyone noticing.
        if stop or kwargs:
            raise ValueError(f"the gateway doesn't support: {sorted([*kwargs, *(['stop'] if stop else [])])}")
        request = ChatRequest(
            model=self.model,
            messages=[to_contract(m) for m in messages],
            tools=tools or [],
            response_schema=response_schema,
            max_tokens=self.max_tokens,
            caller=self.caller,
        )
        response = self.http_client.post(
            f"{self.base_url}{CHAT_PATH}",
            json=request.model_dump(mode="json"),
            headers=self._headers(),
            timeout=self.timeout_s,
        )
        # TODO [LLM:MEDIUM] retry 429/5xx with backoff; today the job fails and the queue retries it.
        response.raise_for_status()
        answer = from_contract(ChatResponse.model_validate_json(response.content))
        return ChatResult(generations=[ChatGeneration(message=answer)])

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key.get_secret_value()}"} if self.api_key else {}

    def bind_tools(
        self,
        tools: Sequence[ToolLike],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        # Newer models reject forced tool choice, so the gateway contract has none.
        if tool_choice is not None:
            raise ValueError("the gateway doesn't support tool_choice")
        return self.bind(tools=to_tool_specs(tools), **kwargs)

    def with_structured_output(
        self,
        schema: dict[str, Any] | type,
        *,
        include_raw: bool = False,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, dict[str, Any] | BaseModel]:
        if not (isinstance(schema, type) and issubclass(schema, BaseModel)):
            raise TypeError("structured output takes a Pydantic model class")
        if include_raw or set(kwargs) - {"method"} or kwargs.get("method", JSON_SCHEMA_METHOD) != JSON_SCHEMA_METHOD:
            raise ValueError("the gateway supports only method='json_schema' without include_raw")
        response_schema = ResponseSchema(name=schema.__name__, json_schema=schema.model_json_schema())
        return self.bind(response_schema=response_schema) | RunnableLambda(
            lambda message: schema.model_validate_json(message.text)
        )
