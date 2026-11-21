import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from app.git import list_files, ls_remote, run_git, shallow_clone

TIMEOUT_S = 30


@pytest.fixture
def source_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "source"
    repo.mkdir()
    (repo / "main.py").write_text("print('hi')\n")
    identity = ["-c", "user.name=test", "-c", "user.email=test@example.com"]
    run_git(["init"], TIMEOUT_S, cwd=repo)
    run_git(["add", "."], TIMEOUT_S, cwd=repo)
    run_git([*identity, "commit", "-m", "init"], TIMEOUT_S, cwd=repo)
    return repo


def test_shallow_clone_returns_head_sha_and_temp_dir_is_removed(source_repo: Path) -> None:
    with TemporaryDirectory() as tmp:
        dest = Path(tmp) / "clone"
        # file:// so --depth is honoured (a plain local path ignores it)
        sha = shallow_clone(source_repo.as_uri(), dest, TIMEOUT_S)
        assert (dest / "main.py").exists()
    assert sha == run_git(["rev-parse", "HEAD"], TIMEOUT_S, cwd=source_repo)
    # git writes read-only pack files; on Windows a naive rmtree fails on them
    assert not dest.exists()


def test_ls_remote_accepts_a_readable_repo_and_rejects_a_missing_one(source_repo: Path, tmp_path: Path) -> None:
    assert ls_remote(source_repo.as_uri(), TIMEOUT_S) == run_git(["rev-parse", "HEAD"], TIMEOUT_S, cwd=source_repo)
    with pytest.raises(subprocess.CalledProcessError):
        ls_remote((tmp_path / "missing").as_uri(), TIMEOUT_S)


def test_missing_repo_raises_with_git_reason(tmp_path: Path) -> None:
    with pytest.raises(subprocess.CalledProcessError) as exc:
        shallow_clone((tmp_path / "missing").as_uri(), tmp_path / "clone", TIMEOUT_S)
    assert "fatal:" in exc.value.__notes__[0]


def test_list_files_returns_tracked_paths_verbatim(source_repo: Path) -> None:
    (source_repo / "pkg dir").mkdir()
    (source_repo / "pkg dir" / "café.py").write_text("")
    run_git(["add", "pkg dir"], TIMEOUT_S, cwd=source_repo)
    (source_repo / "untracked.py").write_text("")
    assert sorted(list_files(source_repo, TIMEOUT_S)) == ["main.py", "pkg dir/café.py"]
