import os
from pathlib import Path

import pytest
from langchain_core.messages import ToolMessage

from app.git import list_files, run_git
from app.workspace import ImportGraph, Workspace, load_import_graph, make_workspace_tools

TIMEOUT_S = 30
FILES = {
    "README.md": "# Demo\nA demo service.\n",
    "app/__init__.py": "",
    "app/core.py": 'class Engine:\n    """Runs jobs.\n\n    More text."""\n    def run(self, n: int = 1) -> str:\n        return "x"\n\ndef _private(): ...\n',
    "app/api.py": "from app.core import Engine\n\ndef serve(): return Engine()\n",
    "app/cli.py": "from app import api, core\n\ndef main(*args, **kwargs): ...\n",
    "web/index.ts": "export const x = 1\n",
}


@pytest.fixture(scope="module")
def repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("repo")
    for name, text in FILES.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    run_git(["init"], TIMEOUT_S, cwd=root)
    run_git(["add", "."], TIMEOUT_S, cwd=root)
    return root


@pytest.fixture(scope="module")
def graph(repo: Path) -> ImportGraph:
    return load_import_graph(repo, TIMEOUT_S)


def _call(repo: Path, graph: ImportGraph, tool: str, scope: tuple[str, ...] = (), **args: object) -> ToolMessage:
    workspace = Workspace(root=repo, files=frozenset(list_files(repo, TIMEOUT_S)), scope=scope)
    [found] = [t for t in make_workspace_tools(workspace, graph) if t.name == tool]
    message = found.invoke({"name": tool, "args": args, "id": "c1", "type": "tool_call"})
    assert isinstance(message, ToolMessage)
    return message


def test_import_graph_reads_the_repos_app_package_not_ours(graph: ImportGraph) -> None:
    # The repo's package is called `app`, like ours: only process isolation makes this come out right.
    assert graph.modules == {
        "app": "app/__init__.py", "app.core": "app/core.py", "app.api": "app/api.py", "app.cli": "app/cli.py",
    }
    # `from app import api, core` imports the submodules, not the package itself.
    assert graph.imports["app.cli"] == ["app.api", "app.core"]


def test_tree_shows_folders_counts_and_root_files(repo: Path, graph: ImportGraph) -> None:
    text = _call(repo, graph, "tree").content
    assert "./ (6 files: .py 4, .md 1, .ts 1)" in text
    assert "app/ (4 files: .py 4)" in text
    assert "  README.md" in text


def test_outline_shows_public_signatures_and_docs(repo: Path, graph: ImportGraph) -> None:
    text = _call(repo, graph, "outline", path="app/core.py").content
    assert "class Engine  # Runs jobs." in text
    assert "def run(self, n: int = 1) -> str" in text
    assert "_private" not in text


def test_grep_finds_matches_and_reports_none(repo: Path, graph: ImportGraph) -> None:
    assert "app/api.py:1: from app.core import Engine" in _call(repo, graph, "grep", pattern="import Engine").content
    assert _call(repo, graph, "grep", pattern="nothing_like_this").content == "no matches"


def test_read_file_numbers_lines(repo: Path, graph: ImportGraph) -> None:
    assert _call(repo, graph, "read_file", path="README.md").content == "1: # Demo\n2: A demo service.\n(lines 1-2 of 2)"


def test_imports_and_clusters_use_the_graph(repo: Path, graph: ImportGraph) -> None:
    assert "app.core (app/core.py): imported by 2" in _call(repo, graph, "clusters").content
    assert "imported by:\n  app.api (app/api.py): 1" in _call(repo, graph, "imports", path="app/core.py").content


def test_manifests_shows_readme(repo: Path, graph: ImportGraph) -> None:
    assert _call(repo, graph, "manifests").content.startswith("=== README.md\n# Demo")


@pytest.mark.parametrize("path", ["../etc/passwd", "/etc/passwd", "C:/Windows", "web"])
def test_paths_outside_the_repo_or_scope_are_refused(repo: Path, graph: ImportGraph, path: str) -> None:
    message = _call(repo, graph, "tree", scope=("app",), path=path)
    assert message.status == "error"


def test_bad_arguments_come_back_as_an_explained_error(repo: Path, graph: ImportGraph) -> None:
    message = _call(repo, graph, "read_file", path="README.md", start_line="not a number")
    assert message.status == "error"
    assert "start_line" in message.content


def test_symlink_out_of_the_repo_is_refused(tmp_path: Path, graph: ImportGraph) -> None:
    outside = tmp_path / "secret.txt"
    outside.write_text("secret")
    (tmp_path / "repo").mkdir()
    try:
        os.symlink(outside, tmp_path / "repo" / "link.txt")
    except OSError:
        pytest.skip("creating symlinks needs extra rights on this machine")
    workspace = Workspace(root=tmp_path / "repo", files=frozenset({"link.txt"}))
    [read] = [t for t in make_workspace_tools(workspace, graph) if t.name == "read_file"]
    message = read.invoke({"name": "read_file", "args": {"path": "link.txt"}, "id": "c1", "type": "tool_call"})
    assert message.status == "error"
    assert "outside the repository" in message.content
