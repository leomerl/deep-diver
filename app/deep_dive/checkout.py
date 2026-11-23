from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from app.indexing.code_files import code_files
from app.workspace import Workspace

WHOLE_REPO = ""  # a sparse path that checks out every file

type CloneArea = Callable[[str, str, list[str], Path, int | None], None]  # (url, sha, paths, dest, added_by)
type ListFiles = Callable[[Path], list[str]]


@contextmanager
def checkout(clone: CloneArea, list_files: ListFiles, url: str, sha: str, added_by: int | None) -> Iterator[Workspace]:
    """The whole repo at `sha` in a temp dir, deleted on exit. The whole repo, not just the node's paths: edge cases
    are often settled by callers and imports, and an agent that can't read them guesses."""
    with TemporaryDirectory() as tmp:
        dest = Path(tmp) / "repo"
        clone(url, sha, [WHOLE_REPO], dest, added_by)
        # code_files drops secrets (.env, keys) and vendored files: what the agent reads ends up at the LLM provider.
        yield Workspace(root=dest, files=frozenset(code_files(list_files(dest))))
