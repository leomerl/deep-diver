from pathlib import Path

import pytest

from app.git import run_git, sparse_clone

TIMEOUT_S = 30
IDENTITY = ["-c", "user.name=test", "-c", "user.email=test@example.com"]


@pytest.fixture
def source(tmp_path: Path) -> tuple[Path, str]:
    """A repo with two commits; returns it and the first commit's SHA (no longer the branch tip)."""
    repo = tmp_path / "source"
    for name in ("app/queue/stream.py", "app/top.py", "other/y.py"):
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(f"# {name}\n")
    run_git(["init"], TIMEOUT_S, cwd=repo)
    # Fetching a non-tip SHA and --filter must be allowed, as GitHub and GitLab allow them.
    run_git(["config", "uploadpack.allowAnySHA1InWant", "true"], TIMEOUT_S, cwd=repo)
    run_git(["config", "uploadpack.allowFilter", "true"], TIMEOUT_S, cwd=repo)
    run_git(["add", "."], TIMEOUT_S, cwd=repo)
    run_git([*IDENTITY, "commit", "-m", "one"], TIMEOUT_S, cwd=repo)
    pinned = run_git(["rev-parse", "HEAD"], TIMEOUT_S, cwd=repo)
    (repo / "app/top.py").write_text("# changed after indexing\n")
    run_git([*IDENTITY, "commit", "-am", "two"], TIMEOUT_S, cwd=repo)
    return repo, pinned


def test_checks_out_only_the_paths_at_the_pinned_commit(source: tuple[Path, str], tmp_path: Path) -> None:
    repo, pinned = source
    dest = tmp_path / "dest"

    sparse_clone(repo.as_uri(), pinned, ["app/queue", "app/top.py"], dest, TIMEOUT_S)

    assert (dest / "app/queue/stream.py").exists()
    assert (dest / "app/top.py").read_text() == "# app/top.py\n"
    assert not (dest / "other").exists()


def test_rejects_anything_but_a_full_sha(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="full commit SHA"):
        sparse_clone("https://github.com/o/r", "--upload-pack=evil", ["app"], tmp_path / "d", TIMEOUT_S)
