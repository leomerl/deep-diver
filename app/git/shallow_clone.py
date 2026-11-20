from collections.abc import Mapping
from pathlib import Path

from .run import run_git


def shallow_clone(url: str, dest: Path, timeout_s: float, env: Mapping[str, str] | None = None) -> str:
    """Clone only the latest commit of the default branch into `dest`. Returns its SHA."""
    # `--` ends option parsing: a URL starting with `-` can't become a git flag.
    run_git(["clone", "--depth", "1", "--single-branch", "--", url, str(dest)], timeout_s, env=env)
    return run_git(["rev-parse", "HEAD"], timeout_s, cwd=dest)
