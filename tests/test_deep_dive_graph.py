from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.agent import AgentFailed
from app.deep_dive.answer import AnswerContext, DeepDiveAnswer, Diagram
from app.deep_dive.graph import DeepDiveGraph, build_graph, forget_thread, run_graph
from app.kroki import DiagramLanguage
from app.workspace import Workspace

SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"></svg>'
ANSWER = {
    "title": "The queue",
    "interview_questions": [{"question": f"Why {n}?", "answer": f"Because {n}."} for n in range(3)],
    "sections": [{"heading": "How a job moves", "blocks": [
        {"type": "diagram", "language": "graphviz", "source": "digraph { a -> b }", "caption": "Who calls whom."},
    ]}],
}
NODE = "107"


class Fakes:
    """Agent steps that record calls; `verify_error` makes the verifier raise once."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.renders = 0
        self.verify_error: Exception | None = None

    def render(self, language: DiagramLanguage, source: str) -> str:
        self.renders += 1
        return SVG

    def write(self, workspace: Workspace, task: str, label: str) -> DeepDiveAnswer:
        self.calls.append("write")
        return DeepDiveAnswer.model_validate(ANSWER, context=AnswerContext(workspace, self.render))

    def verify(self, workspace: Workspace, task: str, draft: DeepDiveAnswer, label: str) -> DeepDiveAnswer:
        self.calls.append("verify")
        if self.verify_error is not None:
            error, self.verify_error = self.verify_error, None
            raise error
        return draft.model_copy(update={"title": draft.title + ", verified"})


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    return Workspace(root=tmp_path, files=frozenset())


def _run(fakes: Fakes, graph: DeepDiveGraph, workspace: Workspace) -> DeepDiveAnswer:
    return run_graph(graph, fakes.render, NODE, workspace, "task", "label")


def test_write_then_verify_gives_a_verified_answer_with_rendered_diagrams(workspace: Workspace) -> None:
    fakes = Fakes()
    answer = _run(fakes, build_graph(fakes.write, fakes.verify, InMemorySaver()), workspace)

    assert answer.title == "The queue, verified"
    assert fakes.calls == ["write", "verify"]
    block = answer.sections[0].blocks[0]
    assert isinstance(block, Diagram) and block.svg == SVG


def test_a_failed_verifier_keeps_the_draft(workspace: Workspace) -> None:
    fakes = Fakes()
    fakes.verify_error = AgentFailed("rejected twice")
    assert _run(fakes, build_graph(fakes.write, fakes.verify, InMemorySaver()), workspace).title == "The queue"


def test_a_crash_in_verify_resumes_there_without_rewriting(workspace: Workspace) -> None:
    fakes = Fakes()
    graph = build_graph(fakes.write, fakes.verify, InMemorySaver())
    fakes.verify_error = ConnectionError("kroki down")
    with pytest.raises(ConnectionError):
        _run(fakes, graph, workspace)

    assert _run(fakes, graph, workspace).title == "The queue, verified"
    assert fakes.calls == ["write", "verify", "verify"]


def test_a_finished_thread_is_reused_until_forgotten(workspace: Workspace) -> None:
    fakes = Fakes()
    saver = InMemorySaver()
    graph = build_graph(fakes.write, fakes.verify, saver)
    first = _run(fakes, graph, workspace)
    again = _run(fakes, graph, workspace)

    assert again == first
    assert fakes.calls == ["write", "verify"]  # the second delivery paid for no agent run
    assert fakes.renders == 4  # but did re-render the diagram: write, verify's reload, and one per run_graph result

    forget_thread(saver, NODE)
    _run(fakes, graph, workspace)
    assert fakes.calls == ["write", "verify", "write", "verify"]
