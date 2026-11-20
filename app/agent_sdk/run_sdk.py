import asyncio
from collections.abc import Sequence

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKError,
    ResultError,
    ResultMessage,
    create_sdk_mcp_server,
    query,
)
from langchain_core.tools import BaseTool
from pydantic import BaseModel, TypeAdapter, ValidationError

from app.llm.gateway_contract import JsonObject, Usage

from .agent_sdk_error import AgentSdkError
from .mcp_tools import to_sdk_tools
from .sdk_result import SdkResult
from .settings import AgentSdkSettings

SERVER = "workspace"
JSON_SCHEMA_FORMAT = "json_schema"
OUT_OF_TURNS = "error_max_turns"
BAD_ANSWER = "error_max_structured_output_retries"  # the model never produced schema-valid JSON
# Update checks, telemetry and the like: a worker has no business making them.
BASE_ENV = {"CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}

_answer_adapter = TypeAdapter(JsonObject)


class _ResultPayload(BaseModel):
    """The fields of the CLI's raw result payload needed on the error path (the success path has ResultMessage)."""

    num_turns: int = 0
    total_cost_usd: float | None = None
    usage: Usage | None = None


def run_sdk(
    settings: AgentSdkSettings,
    system: str,
    prompt: str,
    tools: Sequence[BaseTool],
    answer_schema: JsonObject,
    max_turns: int,
    resume: str | None = None,
) -> SdkResult:
    """One Agent SDK run: the model uses `tools` until it answers in `answer_schema`'s shape or runs out of turns.

    `resume` continues an earlier run's session (its history and thinking) with a new prompt. Raises
    AgentSdkError when the binary or the API fails; an unusable answer is a result, not an error, so callers
    can nudge, wrap up or fall back as they do with the gateway.
    """
    options = ClaudeAgentOptions(
        model=settings.model,
        system_prompt=system,
        tools=[],  # none of Claude Code's built-in tools: the given tools are the only way into the repo
        mcp_servers={SERVER: create_sdk_mcp_server(SERVER, tools=to_sdk_tools(tools))},
        # Without these two the binary also loads the host user's MCP servers (one run sent 400k tokens of
        # their tool schemas) and settings files, whose hooks would run code from the repo under analysis.
        strict_mcp_config=True,
        setting_sources=[],
        allowed_tools=[f"mcp__{SERVER}__{tool.name}" for tool in tools],
        output_format={"type": JSON_SCHEMA_FORMAT, "schema": answer_schema},
        max_turns=max_turns,
        resume=resume,
        env={**BASE_ENV, **settings.env},
    )
    try:
        # One event loop per call: callers run agents from worker threads, and each run is its own process.
        message = asyncio.run(_last_message(prompt, options))
    except ResultError as e:
        # The CLI reports "no answer" outcomes as error results; depending on its exit code they arrive
        # as this exception or as the ResultMessage below, so both paths share _no_answer.
        payload = _ResultPayload.model_validate(e.data)
        return _no_answer(e.subtype, e.session_id, payload.num_turns, payload.usage, payload.total_cost_usd, e)
    except ClaudeSDKError as e:
        raise AgentSdkError(str(e)) from e
    usage = Usage.model_validate(message.usage) if message.usage else None
    if message.is_error:
        return _no_answer(message.subtype, message.session_id, message.num_turns, usage, message.total_cost_usd)
    return SdkResult(
        answer=_answer(message.structured_output),
        out_of_turns=False,
        session_id=message.session_id,
        turns=message.num_turns,
        usage=_usage(usage),
        cost_usd=message.total_cost_usd,
    )


async def _last_message(prompt: str, options: ClaudeAgentOptions) -> ResultMessage:
    result: ResultMessage | None = None
    # Read the stream to its end: leaving the generator open makes asyncio.run close it while it runs.
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            result = message
    if result is None:
        raise AgentSdkError("the run ended without a result message")
    return result


def _no_answer(
    subtype: str,
    session_id: str | None,
    turns: int,
    usage: Usage | None,
    cost_usd: float | None,
    cause: ResultError | None = None,
) -> SdkResult:
    """An error result the model is responsible for becomes a result; anything else (API, process) raises."""
    if subtype not in (OUT_OF_TURNS, BAD_ANSWER):
        raise AgentSdkError(f"{subtype}: {cause.result or cause.errors if cause else 'error result'}") from cause
    return SdkResult(
        answer=None,
        out_of_turns=subtype == OUT_OF_TURNS,
        session_id=session_id,
        turns=turns,
        usage=_usage(usage),
        cost_usd=cost_usd,
    )


def _answer(structured_output: object) -> JsonObject | None:
    if structured_output is None:
        return None  # the model ended its turn without answering; the caller nudges
    try:
        return _answer_adapter.validate_python(structured_output)
    except ValidationError as e:
        raise AgentSdkError(f"the answer is not a JSON object: {e}") from e


def _usage(usage: Usage | None) -> Usage:
    if usage is None:
        return Usage(input_tokens=0, output_tokens=0)
    # Gateway convention (app/gateway/from_anthropic.py): input_tokens counts the cached part too.
    cached = usage.cache_read_input_tokens + usage.cache_creation_input_tokens
    return usage.model_copy(update={"input_tokens": usage.input_tokens + cached})
