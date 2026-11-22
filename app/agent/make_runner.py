import uuid
from collections.abc import Callable, Sequence

from langchain_core.tools import BaseTool
from pydantic import BaseModel, SecretStr

from app.agent_sdk import AgentSdkSettings, run_sdk
from app.config import AGENT_RUNTIMES, LLM_GATEWAY_KEY, LLM_GATEWAY_URL, LLM_MAX_TOKENS, LLM_TIMEOUT_S
from app.llm.gateway_chat_model import GatewayChatModel
from app.llm.gateway_contract import Caller

from .agent_runner import AgentRunner
from .agent_runtime import AgentRuntime
from .dispatch_runner import dispatch_runner
from .run_agent import run_agent
from .run_agent_sdk import run_agent_sdk

RUNTIME_SEPARATOR = ","


def make_runner(model_name: str, selected: Callable[[], AgentRuntime]) -> AgentRunner:
    """Every runtime AGENT_RUNTIMES allows, bound to one model; `selected` (the dashboard setting) picks per call.

    Parses AGENT_RUNTIMES here, so a typo fails at startup. The gateway is always built: it is the fallback.
    """
    allowed = {AgentRuntime(name.strip()) for name in AGENT_RUNTIMES.split(RUNTIME_SEPARATOR)}
    runners = {AgentRuntime.gateway: _gateway_runner(model_name)}
    if AgentRuntime.agent_sdk in allowed:
        runners[AgentRuntime.agent_sdk] = _sdk_runner(model_name)
    return dispatch_runner(runners, selected)


def _sdk_runner(model_name: str) -> AgentRunner:
    # Empty env: the Claude Code binary uses the login of the host it runs on. Only for workers run on a
    # developer's own machine; the compose workers have no login and keep the gateway (DESIGN.md §2).
    settings = AgentSdkSettings(model=model_name)

    def run[T: BaseModel](
        system: str, task: str, tools: Sequence[BaseTool], answer: type[T], max_turns: int,
        wrap_up_turns: int, label: str, context: object | None = None,
    ) -> T:
        return run_agent_sdk(run_sdk, settings, system, task, tools, answer, max_turns, wrap_up_turns, label, context)

    return run


def _gateway_runner(model_name: str) -> AgentRunner:
    model = GatewayChatModel(
        base_url=LLM_GATEWAY_URL,
        model=model_name,
        max_tokens=LLM_MAX_TOKENS,
        timeout_s=LLM_TIMEOUT_S,
        api_key=SecretStr(LLM_GATEWAY_KEY) if LLM_GATEWAY_KEY else None,
    )

    def run[T: BaseModel](
        system: str, task: str, tools: Sequence[BaseTool], answer: type[T], max_turns: int,
        wrap_up_turns: int, label: str, context: object | None = None,
    ) -> T:
        # A copy per run (same HTTP pool): the gateway's usage rows can then tell two runs of one label apart.
        run_model = model.model_copy(update={"caller": Caller(label=label, run_id=uuid.uuid4())})
        return run_agent(run_model, system, task, tools, answer, max_turns, wrap_up_turns, label, context)

    return run
