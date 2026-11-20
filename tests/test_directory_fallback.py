from pathlib import Path

from app.indexing.directory_fallback import directory_fallback
from app.models import Grouping
from app.workspace import Workspace

FILES = frozenset({"README.md", "app/main.py", "app/auth/login.py", "app/billing/pay.py", "web/index.ts"})


def test_children_are_the_immediate_subfolders_marked_fallback() -> None:
    nodes = directory_fallback(Workspace(root=Path("."), files=FILES, scope=("app",)))

    assert [(n.name, n.paths, n.grouping) for n in nodes] == [
        ("auth", ["app/auth"], Grouping.fallback), ("billing", ["app/billing"], Grouping.fallback),
    ]


def test_whole_repo_falls_back_to_top_level_folders() -> None:
    assert [n.paths for n in directory_fallback(Workspace(root=Path("."), files=FILES))] == [["app"], ["web"]]
