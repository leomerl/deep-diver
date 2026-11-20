"""Index a local folder without the queue or a remote: python -m app.indexing.index_local <folder> <url>

For trying the indexer on a repo that isn't pushed anywhere (e.g. this one). The folder is copied into a fresh
git repo, so the agents see exactly what a clone would give them; <url> is only the key the repo is saved under.
"""
import logging
import shutil
import sys
from functools import partial
from pathlib import Path

from sqlmodel import Session

from app.config import engine
from app.git import list_files, run_git
from app.indexing.index_repo import index_repo
from app.indexing.make_explore import make_explore
from app.models import IndexJob

GIT_TIMEOUT_S = 60
# Never part of a snapshot: environments, caches and an existing git directory.
SKIPPED = shutil.ignore_patterns(".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache")
SNAPSHOT_IDENTITY = ["-c", "user.name=deep-diver", "-c", "user.email=deep-diver@localhost"]


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    folder, job = Path(sys.argv[1]).resolve(), IndexJob(url=sys.argv[2])
    with Session(engine) as session:
        index_repo(session, job, partial(_snapshot, folder), partial(list_files, timeout_s=GIT_TIMEOUT_S), make_explore())
    logging.info("indexed %s from %s", job.url, folder)


def _snapshot(folder: Path, url: str, dest: Path) -> str:
    """A `Clone` that copies `folder` into a new one-commit repo at `dest` and returns that commit's SHA."""
    shutil.copytree(folder, dest, ignore=SKIPPED)
    run_git(["init", "-q"], GIT_TIMEOUT_S, cwd=dest)
    run_git(["add", "-A"], GIT_TIMEOUT_S, cwd=dest)
    run_git([*SNAPSHOT_IDENTITY, "commit", "-q", "-m", "snapshot"], GIT_TIMEOUT_S, cwd=dest)
    return run_git(["rev-parse", "HEAD"], GIT_TIMEOUT_S, cwd=dest)


if __name__ == "__main__":
    main()
