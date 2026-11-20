from dataclasses import dataclass

from app.llm.gateway_contract import JsonObject, Usage


@dataclass(frozen=True)
class SdkResult:
    answer: JsonObject | None  # None: the run ended without a usable answer
    out_of_turns: bool  # the run hit max_turns, so a wrap-up resume makes sense
    session_id: str | None  # handle for resuming the run; None when the CLI reported none
    turns: int
    usage: Usage
    cost_usd: float | None  # the SDK's client-side estimate, not a bill
