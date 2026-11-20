from collections.abc import Iterator, Sequence
from typing import Self

import pytest
from langchain_core.language_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, ValidationInfo, field_validator

from app.agent import AgentFailed, run_agent


class ScriptedModel(GenericFakeChatModel):
    """Replies with scripted messages in order and records what it was sent."""

    seen: list[list[BaseMessage]] = []

    def bind_tools(self, tools: Sequence[object], **kwargs: object) -> Self:
        return self

    def invoke(self, messages: list[BaseMessage], *args: object, **kwargs: object) -> AIMessage:  # type: ignore[override]  # test double records its input
        self.seen.append(list(messages))
        return super().invoke(messages, *args, **kwargs)


class Answer(BaseModel):
    """Submit the final answer."""

    path: str

    @field_validator("path")
    @classmethod
    def _must_exist(cls, path: str, info: ValidationInfo) -> str:
        if info.context is None or path not in info.context["files"]:
            raise ValueError(f"{path} does not exist")
        return path


@tool
def tree() -> str:
    """Show the tree."""
    return "app/"


def _model(*replies: AIMessage) -> ScriptedModel:
    replies_iter: Iterator[AIMessage] = iter(replies)
    return ScriptedModel(messages=replies_iter, seen=[])


def _call(name: str, call_id: str, **args: object) -> AIMessage:
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": call_id}])


def _run(model: ScriptedModel, tools: Sequence[BaseTool] = (tree,), max_turns: int = 10, wrap_up: int = 2) -> Answer:
    context = {"files": {"app/x.py"}}
    return run_agent(model, "system", "task", tools, Answer, max_turns, wrap_up, "test", context=context)


def test_runs_tools_then_returns_the_valid_answer() -> None:
    model = _model(_call("tree", "c1"), _call("Answer", "c2", path="app/x.py"))

    assert _run(model) == Answer.model_validate({"path": "app/x.py"}, context={"files": {"app/x.py"}})
    tool_result = model.seen[1][-1]
    assert (tool_result.type, tool_result.content) == ("tool", "app/")


def test_rejected_answer_is_fed_back_once_and_can_be_fixed() -> None:
    model = _model(_call("Answer", "c1", path="nope.py"), _call("Answer", "c2", path="app/x.py"))

    assert _run(model).path == "app/x.py"
    feedback = model.seen[1][-1]
    assert feedback.type == "tool" and "nope.py does not exist" in feedback.content


def test_second_rejection_fails_the_agent() -> None:
    model = _model(_call("Answer", "c1", path="nope.py"), _call("Answer", "c2", path="still_nope.py"))
    with pytest.raises(AgentFailed, match="rejected 2 times"):
        _run(model)


def test_out_of_turns_the_agent_is_told_to_wrap_up_and_can_still_answer() -> None:
    model = _model(_call("tree", "c1"), _call("tree", "c2"), _call("Answer", "c3", path="app/x.py"))

    assert _run(model, max_turns=2, wrap_up=1).path == "app/x.py"
    assert "You have 1 more turns" in model.seen[2][-1].content


def test_ignoring_the_wrap_up_fails_the_agent() -> None:
    model = _model(*[_call("tree", f"c{i}") for i in range(4)])
    with pytest.raises(AgentFailed, match="wrap-up turns"):
        _run(model, max_turns=2, wrap_up=2)


def test_unknown_tool_and_text_replies_are_answered_not_fatal() -> None:
    model = _model(_call("rm_rf", "c1"), AIMessage("thinking out loud"), _call("Answer", "c2", path="app/x.py"))

    assert _run(model).path == "app/x.py"
    assert "unknown tool 'rm_rf'" in model.seen[1][-1].content
    assert "give your final answer by calling Answer" in model.seen[2][-1].content
