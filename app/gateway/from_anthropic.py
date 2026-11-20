from anthropic.types.beta import BetaMessage, BetaTextBlock, BetaToolUseBlock

from app.llm.gateway_contract import ChatResponse, Message, Role, StopReason, ToolCall, Usage

STOP_REASONS = {
    "end_turn": StopReason.end_turn,
    "stop_sequence": StopReason.end_turn,
    "tool_use": StopReason.tool_use,
    "max_tokens": StopReason.max_tokens,
    "model_context_window_exceeded": StopReason.max_tokens,  # cut off too: the answer is incomplete
    "refusal": StopReason.refusal,
}


def from_anthropic(message: BetaMessage) -> ChatResponse:
    """An Anthropic message -> the contract's response. Thinking and fallback blocks are not carried.

    Raises ValueError on a stop reason the contract has no meaning for (e.g. pause_turn, which only server-side
    tools produce, and we declare none).
    """
    stop = STOP_REASONS.get(message.stop_reason or "")
    if stop is None:
        raise ValueError(f"unexpected stop_reason {message.stop_reason!r}")
    usage = message.usage
    cache_read, cache_creation = usage.cache_read_input_tokens or 0, usage.cache_creation_input_tokens or 0
    # The cached part of the prompt is still input the model read: input_tokens counts it, the cache fields split it.
    input_tokens = usage.input_tokens + cache_read + cache_creation
    return ChatResponse(
        message=Message(
            role=Role.assistant,
            content="".join(block.text for block in message.content if isinstance(block, BetaTextBlock)),
            tool_calls=[
                ToolCall(id=block.id, name=block.name, arguments=block.input)
                for block in message.content
                if isinstance(block, BetaToolUseBlock)
            ],
        ),
        stop_reason=stop,
        usage=Usage(
            input_tokens=input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_input_tokens=cache_read,
            cache_creation_input_tokens=cache_creation,
        ),
    )
