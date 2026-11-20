from enum import StrEnum


class StopReason(StrEnum):
    end_turn = "end_turn"
    tool_use = "tool_use"  # the caller runs the tools and sends results back as tool messages
    max_tokens = "max_tokens"  # cut off: the message is incomplete
    refusal = "refusal"  # the provider declined; content may not match the response schema
