from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.deep_dive.answer import AnswerContext, NotebookAnswer
from app.deep_dive.generate_notebook import generate_notebook
from app.models import DeepDive, Node, NotebookBase, NotebookJob, Repo, RepoStatus, Snapshot
from app.workspace import Workspace

SHA = "a" * 40
FILES = {"app/queue/stream.py": "def enqueue():\n    pass\n", ".env": "KEY=secret\n"}
PAGE = '<html><head><style>p{}</style></head><body><h1>The queue</h1><p>Jobs wait.</p><svg><text>x</text></svg></body></html>'


class Fakes:
    def __init__(self) -> None:
        self.clones: list[tuple[str, str]] = []
        self.calls: list[tuple[str, str, str]] = []  # (task, page, label)
        self.readable: frozenset[str] = frozenset()
        self.stored: list[NotebookBase] = []

    def clone(self, url: str, sha: str, paths: list[str], dest: Path, added_by: int | None) -> None:
        self.clones.append((url, sha))
        for name, text in FILES.items():
            (dest / name).parent.mkdir(parents=True, exist_ok=True)
            (dest / name).write_text(text)

    def list_files(self, dest: Path) -> list[str]:
        return sorted(FILES)

    def read_page(self, key: str) -> str:
        assert key == "page.html"
        return PAGE

    def write(self, workspace: Workspace, task: str, page: str, label: str) -> NotebookAnswer:
        self.calls.append((task, page, label))
        self.readable = workspace.files
        cells = [{"explanation": "Enqueue twice.", "code": "print(1)", "mirrors": "app/queue/stream.py"}] * 2
        return NotebookAnswer.model_validate(
            {"title": "Run the queue", "cells": cells}, context=AnswerContext(workspace, lambda language, source: "<svg/>")
        )

    def store(self, notebook: NotebookBase) -> str:
        self.stored.append(notebook)
        return "nb.json"


@pytest.fixture
def deep_dive(session: Session) -> int:
    repo = Repo(url="https://github.com/o/r", status=RepoStatus.indexed)
    session.add(repo)
    session.flush()
    assert repo.id is not None
    snapshot = Snapshot(repo_id=repo.id, commit_sha=SHA)
    session.add(snapshot)
    session.flush()
    assert snapshot.id is not None
    node = Node(name="Queue", paths=["app/queue"], snapshot_id=snapshot.id)
    session.add(node)
    session.flush()
    row = DeepDive(snapshot_id=snapshot.id, node_id=node.id, object_key="page.html")
    session.add(row)
    session.commit()
    assert row.id is not None
    return row.id


def _run(session: Session, fakes: Fakes, deep_dive_id: int) -> None:
    generate_notebook(session, NotebookJob(deep_dive_id=deep_dive_id), fakes.clone, fakes.list_files, fakes.read_page, fakes.write, fakes.store)


def test_writes_the_notebook_from_the_page_and_a_repeat_is_a_noop(session: Session, deep_dive: int) -> None:
    fakes = Fakes()

    _run(session, fakes, deep_dive)
    _run(session, fakes, deep_dive)

    row = session.exec(select(DeepDive)).one()
    assert row.notebook_key == "nb.json"
    assert [n.title for n in fakes.stored] == ["Run the queue"]  # the repeat found the key and ran no agent
    assert fakes.clones == [("https://github.com/o/r", SHA)]  # the page's own commit
    [(task, page, label)] = fakes.calls
    assert page == "The queue\n\nJobs wait."  # the page's text: no styles, no diagram markup
    assert label == "r > Queue"
    assert "Your area (write about these paths): app/queue" in task  # the same task the writer had
    assert fakes.readable == {"app/queue/stream.py"}  # secrets never reach the agent


def test_a_missing_page_is_dropped(session: Session) -> None:
    fakes = Fakes()
    _run(session, fakes, 999)
    assert fakes.clones == [] and fakes.stored == []
