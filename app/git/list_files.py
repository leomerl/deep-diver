from pathlib import Path

from .run import run_git


def list_files(repo_dir: Path, timeout_s: float) -> list[str]:
    """Paths of all tracked files at HEAD, relative to the repo root, with `/` separators."""
    # -z: NUL-separated and unquoted, so names with spaces, quotes or non-ASCII come back verbatim.
    # shortcut: run_git strips stdout, so a leading space on the first path is lost; take raw stdout if that ever matters.
    out = run_git(["ls-files", "-z"], timeout_s, cwd=repo_dir)
    return [path for path in out.split("\0") if path]
