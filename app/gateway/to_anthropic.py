from anthropic import Omit, omit, transform_schema
from anthropic.types.beta import (
    BetaMessageParam,
    BetaOutputConfigParam,
    BetaTextBlockParam,
    BetaToolParam,
    BetaToolResultBlockParam,
    BetaToolUseBlockParam,
)

from app.llm.gateway_contract import Message, ResponseSchema, Role, ToolSpec

SYSTEM_SEPARATOR = "\n\n"
JSON_SCHEMA_FORMAT = "json_schema"


def system_prompt(messages: list[Message]) -> str | Omit:
    """The leading system messages become the top-level system prompt; later ones stay in place."""
    leading = [m.content for m in _leading_system(messages)]
    return SYSTEM_SEPARATOR.join(leading) if leading else omit


def anthropic_messages(messages: list[Message]) -> list[BetaMessageParam]:
    params: list[BetaMessageParam] = []
    for message in messages[len(_leading_system(messages)):]:
        match message.role:
            case Role.system:
                params.append({"role": "system", "content": message.content})
            case Role.user:
                params.append({"role": "user", "content": message.content})
            case Role.assistant:
                content = _assistant_content(message)
                # A turn with no text and no tool calls (e.g. only thinking, which the contract doesn't carry) has
                # nothing to send, and an empty content list is rejected.
                if content:
                    params.append({"role": "assistant", "content": content})
            case Role.tool:
                _add_tool_result(params, message)
    return params


def anthropic_tools(tools: list[ToolSpec]) -> list[BetaToolParam] | Omit:
    return [{"name": t.name, "description": t.description, "input_schema": t.parameters} for t in tools] or omit


def output_config(schema: ResponseSchema | None) -> BetaOutputConfigParam | Omit:
    if schema is None:
        return omit
    # transform_schema adds additionalProperties: false and moves constraints structured output can't enforce
    # (minLength, minimum...) into the description, as the SDK's own parse() does.
    return {"format": {"type": JSON_SCHEMA_FORMAT, "schema": transform_schema(schema.json_schema)}}


def _leading_system(messages: list[Message]) -> list[Message]:
    leading: list[Message] = []
    for message in messages:
        if message.role != Role.system:
            break
        leading.append(message)
    return leading


def _assistant_content(message: Message) -> list[BetaTextBlockParam | BetaToolUseBlockParam]:
    text: list[BetaTextBlockParam | BetaToolUseBlockParam] = (
        [{"type": "text", "text": message.content}] if message.content else []
    )
    calls: list[BetaTextBlockParam | BetaToolUseBlockParam] = [
        {"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments} for call in message.tool_calls
    ]
    return text + calls


def _add_tool_result(params: list[BetaMessageParam], message: Message) -> None:
    if message.tool_call_id is None:
        raise ValueError("a tool message has no tool_call_id")  # the contract already rejects this
    result: BetaToolResultBlockParam = {
        "type": "tool_result", "tool_use_id": message.tool_call_id, "content": message.content,
    }
    # All results of one assistant turn go back in ONE user message; split across messages, the model learns
    # to stop making parallel tool calls.
    last = params[-1] if params else None
    if last is not None and last["role"] == "user" and isinstance(last["content"], list) and _all_results(last):
        last["content"].append(result)
        return
    params.append({"role": "user", "content": [result]})


def _all_results(param: BetaMessageParam) -> bool:
    content = param["content"]
    return isinstance(content, list) and all(
        isinstance(block, dict) and block.get("type") == "tool_result" for block in content
    )
