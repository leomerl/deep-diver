import logging

import pytest
from pydantic import BaseModel

from app.agent import AgentRunner, AgentRuntime, dispatch_runner


class Answer(BaseModel):
    source: str


def _runner(name: str) -> AgentRunner:
    def run[T: BaseModel](system: str, task: str, tools: object, answer: type[T], max_turns: int,
                          wrap_up_turns: int, label: str, context: object | None = None) -> T:
        return answer.model_validate({"source": name})
    return run


def _call(run: AgentRunner) -> Answer:
    return run("system", "task", [], Answer, 5, 2, "test")


def test_each_call_asks_which_runtime_to_use() -> None:
    choices = [AgentRuntime.gateway, AgentRuntime.agent_sdk]
    run = dispatch_runner({AgentRuntime.gateway: _runner("gw"), AgentRuntime.agent_sdk: _runner("sdk")}, lambda: choices.pop(0))
    assert (_call(run).source, _call(run).source) == ("gw", "sdk")


def test_missing_runtime_falls_back_to_the_gateway_with_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    run = dispatch_runner({AgentRuntime.gateway: _runner("gw")}, lambda: AgentRuntime.agent_sdk)
    with caplog.at_level(logging.WARNING):
        assert _call(run).source == "gw"
    assert "agent_sdk is not available" in caplog.text
