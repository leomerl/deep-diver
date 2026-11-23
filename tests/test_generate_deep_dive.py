from pathlib import Path

import pytest
from sqlmodel import Session, col, select

from app.deep_dive.answer import AnswerContext, DeepDiveAnswer
from app.deep_dive.generate_deep_dive import generate_deep_dive
from app.models import DeepDive, DeepDiveCreate, Edge, EdgeKind, Grouping, InterviewQuestion, Node, Repo, RepoStatus, Snapshot
from app.queue import ReportStep
from app.workspace import Workspace

SHA = "a" * 40
QUESTIONS = [{"question": f"Question {n}?", "answer": f"Answer {n}."} for n in range(1, 4)]
FILES = {"app/queue/stream.py": "def enqueue():\n    pass\n", "app/api.py": "x = 1\n", ".env": "KEY=secret\n"}


class Fakes:
    def __init__(self) -> None:
        self.clones: list[tuple[str, str, list[str]]] = []
        self.tasks: list[tuple[str, str]] = []
        self.pages: list[str] = []
        self.written: list[str] = []
        self.forgotten: list[str] = []
        self.readable: frozenset[str] = frozenset()
        self.notebooks_queued: list[int] = []

    def clone(self, url: str, sha: str, paths: list[str], dest: Path, added_by: int | None) -> None:
        self.clones.append((url, sha, paths))
        for name, text in FILES.items():
            (dest / name).parent.mkdir(parents=True, exist_ok=True)
            (dest / name).write_text(text)

    def list_files(self, dest: Path) -> list[str]:
        return sorted(FILES)

    def write(self, key: str, workspace: Workspace, task: str, label: str, report_step: ReportStep) -> DeepDiveAnswer:
        self.tasks.append((task, label))
        self.written.append(key)
        self.readable = workspace.files
        return self._answer(workspace)

    def _answer(self, workspace: Workspace) -> DeepDiveAnswer:
        return DeepDiveAnswer.model_validate({"title": "The queue", "interview_questions": QUESTIONS, "sections": [{"heading": "How enqueue writes a job", "blocks": [
            {"type": "code", "path": "app/queue/stream.py", "start_line": 1, "end_line": 2, "caption": "Enqueue"},
            {"type": "diagram", "language": "mermaid", "source": "graph TD; a-->b", "caption": "The path"},
        ]}]}, context=AnswerContext(workspace, lambda language, source: "<svg/>"))

    def store(self, html: str) -> str:
        self.pages.append(html)
        return "abc.html"

    def enqueue_notebook(self, deep_dive_id: int) -> bool:
        self.notebooks_queued.append(deep_dive_id)
        return True

    def forget(self, key: str) -> None:
        self.forgotten.append(key)


@pytest.fixture
def leaf(session: Session) -> int:
    repo = Repo(url="https://github.com/o/r", status=RepoStatus.indexed)
    session.add(repo)
    session.flush()
    assert repo.id is not None
    snapshot = Snapshot(repo_id=repo.id, commit_sha=SHA)
    session.add(snapshot)
    session.flush()
    assert snapshot.id is not None
    repo.current_snapshot_id = snapshot.id
    app = Node(name="App", paths=["app"], grouping=Grouping.llm, snapshot_id=snapshot.id)
    queue = Node(name="Queue", description="Jobs.", paths=["app/queue"], grouping=Grouping.llm, snapshot_id=snapshot.id)
    session.add_all([app, queue])
    session.flush()
    assert app.id is not None and queue.id is not None
    session.add(Edge(source_id=app.id, target_id=queue.id, kind=EdgeKind.contains))
    session.commit()
    return queue.id


def _run(session: Session, fakes: Fakes, node_id: int | None, snapshot_id: int = 1) -> None:
    job = DeepDiveCreate(snapshot_id=snapshot_id, node_id=node_id)
    generate_deep_dive(
        session, job, fakes.clone, fakes.list_files, fakes.write, fakes.store, fakes.forget, fakes.enqueue_notebook,
        lambda step: None,
    )


def test_saves_row_pointing_at_uploaded_page_and_repeat_is_noop(session: Session, leaf: int) -> None:
    fakes = Fakes()

    _run(session, fakes, leaf)
    _run(session, fakes, leaf)

    [row] = session.exec(select(DeepDive)).all()
    assert (row.snapshot_id, row.node_id, row.object_key, row.notebook_key) == (1, leaf, "abc.html", None)
    assert fakes.notebooks_queued == [row.id, row.id]  # after the commit, and again on the repeat (a no-op once queued)
    assert fakes.clones == [("https://github.com/o/r", SHA, [""])]  # the whole repo
    [(task, label)] = fakes.tasks
    assert label == "r > App > Queue"
    assert "Your area (write about these paths): app/queue" in task
    assert fakes.readable == {"app/queue/stream.py", "app/api.py"}  # callers readable, secrets never
    [page] = fakes.pages
    assert '<span class="k">def</span><span class="w"> </span><span class="nf">enqueue</span>' in page
    assert fakes.written == [str(leaf)]
    assert fakes.forgotten == [str(leaf), str(leaf)]  # after the commit, and again on the no-op repeat
    questions = session.exec(select(InterviewQuestion).order_by(InterviewQuestion.id)).all()
    assert [(q.question, q.deep_dive_id) for q in questions] == [(f"Question {n}?", row.id) for n in range(1, 4)]


def test_node_of_an_older_snapshot_is_written_from_its_own_commit(session: Session, leaf: int) -> None:
    repo = session.exec(select(Repo)).one()
    newer = Snapshot(repo_id=1, commit_sha="b" * 40)
    session.add(newer)
    session.flush()
    repo.current_snapshot_id = newer.id  # a re-index moved on; the leaf belongs to the old snapshot
    session.commit()
    fakes = Fakes()

    _run(session, fakes, leaf)

    assert [sha for _, sha, _ in fakes.clones] == [SHA]


def test_missing_node_is_dropped(session: Session) -> None:
    fakes = Fakes()
    _run(session, fakes, 999)
    assert fakes.clones == [] and session.exec(select(DeepDive)).all() == []


def test_root_deep_dive_lists_top_level_areas_and_lives_beside_node_deep_dives(session: Session, leaf: int) -> None:
    fakes = Fakes()

    _run(session, fakes, leaf)
    _run(session, fakes, None)
    _run(session, fakes, None)

    rows = session.exec(select(DeepDive).order_by(col(DeepDive.id))).all()
    assert [(r.snapshot_id, r.node_id) for r in rows] == [(1, leaf), (1, None)]
    (_, (task, label)) = fakes.tasks
    assert label == "r"
    assert "- App (app): (none)" in task
    assert "Queue" not in task  # a child area, not top-level
    assert fakes.written == [str(leaf), "snapshot-1"]
    assert fakes.forgotten == [str(leaf), "snapshot-1", "snapshot-1"]


def test_missing_repo_is_dropped(session: Session) -> None:
    fakes = Fakes()
    _run(session, fakes, None, snapshot_id=999)
    assert fakes.clones == [] and session.exec(select(DeepDive)).all() == []
