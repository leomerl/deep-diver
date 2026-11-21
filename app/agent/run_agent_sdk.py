import logging
import time
from collections.abc import Sequence
from typing import Protocol

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ValidationError

from app.agent_sdk import AgentSdkSettings, SdkResult
from app.llm.gateway_contract import JsonObject

from .agent_failed import AgentFailed
from .nudges import MAX_ANSWER_ATTEMPTS, NUDGE, REJECTED, WRAP_UP

# The SDK takes the answer through its own tool of this name, so the nudges written for run_agent's answer tool fit.
ANSWER_TOOL = "StructuredOutput"

logger = logging.getLogger(__name__)


class SdkCall(Protocol):
    """app.agent_sdk.run_sdk's shape, injected so tests can script the SDK."""

    def __call__(
        self,
        settings: AgentSdkSettings,
        system: str,
        prompt: str,
        tools: Sequence[BaseTool],
        answer_schema: JsonObject,
        max_turns: int,
        resume: str | None = None,
    ) -> SdkResult: ...


def run_agent_sdk[T: BaseModel](
    call: SdkCall,
    settings: AgentSdkSettings,
    system: str,
    task: str,
    tools: Sequence[BaseTool],
    answer: type[T],
    max_turns: int,
    wrap_up_turns: int,
    label: str,
    context: object | None = None,
) -> T:
    """run_agent's contract on the Claude Agent SDK: the SDK runs the tool loop, this function owns the answer.

    The first run gets `max_turns`. Each follow-up (a rejected answer, a nudge, the wrap-up) resumes the same
    session, history and thinking included, with `wrap_up_turns` more turns. Raises AgentFailed after
    MAX_ANSWER_ATTEMPTS rejections or when a follow-up still brings no answer.
    """
    schema = answer.model_json_schema()
    prompt, budget, resume = task, max_turns, None
    runs = turns = tokens = cache_read = rejected = 0
    cost = 0.0
    started = time.monotonic()
    try:
        while True:
            result = call(settings, system, prompt, tools, schema, budget, resume=resume)
            runs += 1
            turns += result.turns
            tokens += result.usage.input_tokens + result.usage.output_tokens
            cache_read += result.usage.cache_read_input_tokens
            cost += result.cost_usd or 0.0
            if result.answer is None:
                # shortcut: one follow-up run after a run without an answer, whatever the reason; upgrade to a
                # real turn budget if the logs show agents that answer on the third run.
                if runs > 1:
                    raise AgentFailed(f"{label}: no valid answer within {max_turns} + {wrap_up_turns} wrap-up turns")
                prompt = (
                    WRAP_UP.format(turns=wrap_up_turns, answer=ANSWER_TOOL) if result.out_of_turns
                    else NUDGE.format(answer=ANSWER_TOOL)
                )
            else:
                try:
                    return answer.model_validate(result.answer, context=context)
                except ValidationError as e:
                    rejected += 1
                    if rejected >= MAX_ANSWER_ATTEMPTS:
                        raise AgentFailed(f"{label}: answer rejected {rejected} times: {e}") from e
                    prompt = REJECTED.format(answer=ANSWER_TOOL, errors=e)
            if result.session_id is None:
                raise AgentFailed(f"{label}: the SDK reported no session to resume")
            budget, resume = wrap_up_turns, result.session_id
    finally:
        # Same shape as run_agent's line, plus the SDK's cost estimate, so the two runtimes compare in the logs.
        logger.info(
            "agent %s (sdk): %d runs, %d turns, %d rejected answers, %d tokens (%d cache reads), ~$%.4f, %.1fs",
            label, runs, turns, rejected, tokens, cache_read, cost, time.monotonic() - started,
        )
