import logging
import time
from collections.abc import Mapping, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolCall, ToolMessage
from langchain_core.messages.ai import UsageMetadata
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ValidationError

from .agent_failed import AgentFailed
from .nudges import MAX_ANSWER_ATTEMPTS, NUDGE, REJECTED, WRAP_UP

logger = logging.getLogger(__name__)


def run_agent[T: BaseModel](
    model: BaseChatModel,
    system: str,
    task: str,
    tools: Sequence[BaseTool],
    answer: type[T],
    max_turns: int,
    wrap_up_turns: int,
    label: str,
    context: object | None = None,
) -> T:
    """Let the model use `tools` until it calls the `answer` tool with an answer that validates.

    The answer is checked with `answer.model_validate(args, context=context)`, so validators can compare it
    with facts the model can't change (e.g. the real file list). A rejected answer goes back as the tool's
    result, so the model can fix it. After `max_turns` the model is told to wrap up and gets `wrap_up_turns` more;
    a hard stop is still needed, or a confused agent could run forever. Raises AgentFailed after
    MAX_ANSWER_ATTEMPTS rejections or when the wrap-up turns run out.
    """
    by_name = {tool.name: tool for tool in tools}
    bound = model.bind_tools([*tools, answer])
    messages: list[BaseMessage] = [SystemMessage(system), HumanMessage(task)]
    turns = tool_calls = tokens = cache_read = rejected = 0
    started = time.monotonic()
    try:
        while turns < max_turns + wrap_up_turns:
            if turns == max_turns:
                messages.append(HumanMessage(WRAP_UP.format(turns=wrap_up_turns, answer=answer.__name__)))
            turns += 1
            reply = bound.invoke(messages)
            messages.append(reply)
            tokens += reply.usage_metadata["total_tokens"] if reply.usage_metadata else 0
            cache_read += _cache_read(reply.usage_metadata)
            if not reply.tool_calls:
                messages.append(HumanMessage(NUDGE.format(answer=answer.__name__)))
                continue
            for call in reply.tool_calls:
                if call["name"] != answer.__name__:
                    tool_calls += 1
                    messages.append(_run_tool(by_name, call))
                    continue
                try:
                    return answer.model_validate(call["args"], context=context)
                except ValidationError as e:
                    rejected += 1
                    if rejected >= MAX_ANSWER_ATTEMPTS:
                        raise AgentFailed(f"{label}: answer rejected {rejected} times: {e}") from e
                    messages.append(_error(call, REJECTED.format(answer=answer.__name__, errors=e)))
        raise AgentFailed(f"{label}: no valid answer within {max_turns} + {wrap_up_turns} wrap-up turns")
    finally:
        # Real per-agent budgets get set from these numbers after the first runs (DESIGN §7).
        logger.info(
            "agent %s: %d turns, %d tool calls, %d rejected answers, %d tokens (%d cache reads), %.1fs",
            label, turns, tool_calls, rejected, tokens, cache_read, time.monotonic() - started,
        )


def _run_tool(by_name: Mapping[str, BaseTool], call: ToolCall) -> ToolMessage:
    tool = by_name.get(call["name"])
    if tool is None:
        return _error(call, f"unknown tool {call['name']!r}; available: {', '.join(sorted(by_name))}")
    # Invoked with the whole call, a LangChain tool returns a ToolMessage already paired with the call id.
    result = tool.invoke(call)
    if not isinstance(result, ToolMessage):
        raise TypeError(f"tool {tool.name} returned {type(result).__name__}, not a ToolMessage")
    return result


def _error(call: ToolCall, text: str) -> ToolMessage:
    if call["id"] is None:
        raise ValueError(f"tool call {call['name']!r} has no id")
    return ToolMessage(text, tool_call_id=call["id"], status="error")


def _cache_read(usage: UsageMetadata | None) -> int:
    # Cache reads bill at a fraction of fresh input, so this is what tells a run's real cost apart from its token count.
    return (usage.get("input_token_details") or {}).get("cache_read", 0) if usage else 0
