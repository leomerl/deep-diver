from langchain_core.messages import AIMessage
from langchain_core.messages import ToolCall as LangChainToolCall
from langchain_core.messages.ai import InputTokenDetails, UsageMetadata

from app.llm.gateway_contract import ChatResponse, Role, StopReason, ToolCall

from .gateway_answer_error import GatewayAnswerError

# Cut off mid-answer, or declined: either way the message must never be used as if it were complete.
UNUSABLE_STOP_REASONS = frozenset({StopReason.max_tokens, StopReason.refusal})


def from_contract(response: ChatResponse) -> AIMessage:
    """The gateway's answer -> a LangChain AIMessage with its tool calls and token usage."""
    message, usage = response.message, response.usage
    if message.role != Role.assistant:
        raise GatewayAnswerError(f"expected an assistant message, got {message.role}")
    if response.stop_reason in UNUSABLE_STOP_REASONS:
        raise GatewayAnswerError(f"answer unusable: stop_reason={response.stop_reason}")
    return AIMessage(
        content=message.content,
        tool_calls=[_tool_call(call) for call in message.tool_calls],
        usage_metadata=UsageMetadata(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.input_tokens + usage.output_tokens,
            input_token_details=InputTokenDetails(
                cache_read=usage.cache_read_input_tokens, cache_creation=usage.cache_creation_input_tokens
            ),
        ),
        response_metadata={"stop_reason": response.stop_reason.value},
    )


def _tool_call(call: ToolCall) -> LangChainToolCall:
    return LangChainToolCall(name=call.name, args=call.arguments, id=call.id)
