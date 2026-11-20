from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.deep_dive.answer import AnswerContext, DeepDiveAnswer
from app.deep_dive.generate_deep_dive import generate_deep_dive
from app.models import DeepDive, DeepDiveCreate, Edge, EdgeKind, Grouping, InterviewQuestion, Node, Repo, RepoStatus
from app.workspace import Workspace

SHA = "a" * 40
QUESTIONS = [{"question": f"Question {n}?", "answer": f"Answer {n}."} for n in range(1, 4)]
FILES = {"app/queue/stream.py": "def enqueue():\n    pass\n", "app/api.py": "x = 1\n", ".env": "KEY=secret\n"}


class Fakes:
    def __init__(self) -> None:
        self.clones: list[tuple[str, str, list[str]]] = []
        self.tasks: list[tuple[str, str]] = []
        self.pages: list[str] = []
        self.written: list[int] = []
        self.forgotten: list[int] = []
        self.readable: frozenset[str] = frozenset()

    def clone(self, url: str, sha: str, paths: list[str], dest: Path, added_by: int | None) -> None:
        self.clones.append((url, sha, paths))
        for name, text in FILES.items():
            (dest / name).parent.mkdir(parents=True, exist_ok=True)
            (dest / name).write_text(text)

    def list_files(self, dest: Path) -> list[str]:
        return sorted(FILES)

    def write(self, node_id: int, workspace: Workspace, task: str, label: str) -> DeepDiveAnswer:
        self.tasks.append((task, label))
        self.written.append(node_id)
        self.readable = workspace.files
        return DeepDiveAnswer.model_validate({"title": "The queue", "interview_questions": QUESTIONS, "sections": [{"heading": "How enqueue writes a job", "blocks": [
            {"type": "code", "path": "app/queue/stream.py", "start_line": 1, "end_line": 2, "caption": "Enqueue"},
            {"type": "diagram", "language": "mermaid", "source": "graph TD; a-->b", "caption": "The path"},
        ]}]}, context=AnswerContext(workspace, lambda language, source: "<svg/>"))

    def store(self, html: str) -> str:
        self.pages.append(html)
        return "abc.html"

    def forget(self, node_id: int) -> None:
        self.forgotten.append(node_id)


@pytest.fixture
def leaf(session: Session) -> int:
    repo = Repo(url="https://github.com/o/r", commit_sha=SHA, status=RepoStatus.indexed)
    session.add(repo)
    session.flush()
    assert repo.id is not None
    app = Node(name="App", paths=["app"], grouping=Grouping.llm, repo_id=repo.id)
    queue = Node(name="Queue", description="Jobs.", paths=["app/queue"], grouping=Grouping.llm, repo_id=repo.id)
    session.add_all([app, queue])
    session.flush()
    assert app.id is not None and queue.id is not None
    session.add(Edge(source_id=app.id, target_id=queue.id, kind=EdgeKind.contains))
    session.commit()
    return queue.id


def _run(session: Session, fakes: Fakes, node_id: int) -> None:
    generate_deep_dive(session, DeepDiveCreate(node_id=node_id), fakes.clone, fakes.list_files, fakes.write, fakes.store, fakes.forget)


def test_saves_row_pointing_at_uploaded_page_and_repeat_is_noop(session: Session, leaf: int) -> None:
    fakes = Fakes()

    _run(session, fakes, leaf)
    _run(session, fakes, leaf)

    [row] = session.exec(select(DeepDive)).all()
    assert (row.node_id, row.object_key) == (leaf, "abc.html")
    assert fakes.clones == [("https://github.com/o/r", SHA, [""])]  # the whole repo
    [(task, label)] = fakes.tasks
    assert label == "r > App > Queue"
    assert "Your area (write about these paths): app/queue" in task
    assert fakes.readable == {"app/queue/stream.py", "app/api.py"}  # callers readable, secrets never
    [page] = fakes.pages
    assert "def enqueue():" in page
    assert fakes.written == [leaf]
    assert fakes.forgotten == [leaf, leaf]  # after the commit, and again on the no-op repeat
    questions = session.exec(select(InterviewQuestion).order_by(InterviewQuestion.id)).all()
    assert [(q.question, q.deep_dive_id) for q in questions] == [(f"Question {n}?", row.id) for n in range(1, 4)]


def test_missing_node_is_dropped(session: Session) -> None:
    fakes = Fakes()
    _run(session, fakes, 999)
    assert fakes.clones == [] and session.exec(select(DeepDive)).all() == []
