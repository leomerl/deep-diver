from collections.abc import Sequence

import pytest
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ValidationInfo, field_validator

from app.agent import AgentFailed, run_agent_sdk
from app.agent_sdk import AgentSdkSettings, SdkResult
from app.llm.gateway_contract import JsonObject, Usage

SETTINGS = AgentSdkSettings(model="test-model")
CONTEXT = {"files": {"app/x.py"}}
MAX_TURNS, WRAP_UP = 5, 2


class Answer(BaseModel):
    file: str

    @field_validator("file")
    @classmethod
    def known(cls, value: str, info: ValidationInfo) -> str:
        if value not in info.context["files"]:
            raise ValueError(f"unknown file {value!r}")
        return value


class ScriptedSdk:
    """Plays back SdkResults in order and records what each call asked for."""

    def __init__(self, *results: SdkResult) -> None:
        self.results = list(results)
        self.calls: list[tuple[str, int, str | None]] = []  # (prompt, max_turns, resume)

    def __call__(
        self, settings: AgentSdkSettings, system: str, prompt: str, tools: Sequence[BaseTool],
        answer_schema: JsonObject, max_turns: int, resume: str | None = None,
    ) -> SdkResult:
        assert settings is SETTINGS and system == "system" and "file" in answer_schema["properties"]
        self.calls.append((prompt, max_turns, resume))
        return self.results.pop(0)


def _result(answer: JsonObject | None = None, out_of_turns: bool = False, session: str | None = "s1") -> SdkResult:
    return SdkResult(
        answer=answer, out_of_turns=out_of_turns, session_id=session, turns=2,
        usage=Usage(input_tokens=10, output_tokens=5), cost_usd=0.01,
    )


def _run(sdk: ScriptedSdk) -> Answer:
    return run_agent_sdk(sdk, SETTINGS, "system", "task", [], Answer, MAX_TURNS, WRAP_UP, "test", context=CONTEXT)


def test_valid_answer_returns_after_one_run() -> None:
    sdk = ScriptedSdk(_result({"file": "app/x.py"}))
    assert _run(sdk).file == "app/x.py"
    assert sdk.calls == [("task", MAX_TURNS, None)]


def test_rejected_answer_resumes_the_session_with_the_errors() -> None:
    sdk = ScriptedSdk(_result({"file": "nope.py"}), _result({"file": "app/x.py"}))
    assert _run(sdk).file == "app/x.py"
    prompt, max_turns, resume = sdk.calls[1]
    assert prompt.startswith("Answer rejected") and "unknown file 'nope.py'" in prompt
    assert (max_turns, resume) == (WRAP_UP, "s1")


def test_second_rejection_fails() -> None:
    sdk = ScriptedSdk(_result({"file": "nope.py"}), _result({"file": "nope.py"}))
    with pytest.raises(AgentFailed, match="rejected 2 times"):
        _run(sdk)


def test_out_of_turns_gets_a_wrap_up_run() -> None:
    sdk = ScriptedSdk(_result(out_of_turns=True), _result({"file": "app/x.py"}))
    assert _run(sdk).file == "app/x.py"
    prompt, max_turns, resume = sdk.calls[1]
    assert prompt.startswith("You have used your exploration budget") and f"{WRAP_UP} more turns" in prompt
    assert (max_turns, resume) == (WRAP_UP, "s1")


def test_no_answer_without_running_out_gets_a_nudge() -> None:
    sdk = ScriptedSdk(_result(), _result({"file": "app/x.py"}))
    assert _run(sdk).file == "app/x.py"
    assert sdk.calls[1][0].startswith("Keep exploring")


def test_no_answer_after_the_follow_up_fails() -> None:
    sdk = ScriptedSdk(_result(out_of_turns=True), _result(out_of_turns=True))
    with pytest.raises(AgentFailed, match="wrap-up turns"):
        _run(sdk)


def test_no_session_to_resume_fails_instead_of_starting_over() -> None:
    sdk = ScriptedSdk(_result(out_of_turns=True, session=None))
    with pytest.raises(AgentFailed, match="no session"):
        _run(sdk)
    assert len(sdk.calls) == 1
