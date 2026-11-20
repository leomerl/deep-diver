import re
from collections.abc import Mapping
from pathlib import Path

from .run import run_git

SHA = re.compile(r"[0-9a-f]{40}")
WHOLE_REPO_PATTERN = "/*"


def sparse_clone(
    url: str, sha: str, paths: list[str], dest: Path, timeout_s: float, env: Mapping[str, str] | None = None
) -> None:
    """Check out only `paths` (files or folder prefixes) at commit `sha` into `dest`.

    Fetches one commit, with no blobs up front: git downloads file contents only for the paths it checks out.
    """
    if not SHA.fullmatch(sha):
        raise ValueError(f"not a full commit SHA: {sha!r}")
    run_git(["init", "--quiet", str(dest)], timeout_s)
    # `--` ends option parsing: a URL starting with `-` can't become a git flag. A named remote is needed:
    # with --filter, git fetches missing blobs lazily from it during checkout.
    run_git(["remote", "add", "origin", "--", url], timeout_s, cwd=dest)
    # Non-cone patterns, so a path can be a single file. The leading `/` anchors each at the repo root and
    # also means no pattern can start with `-`.
    patterns = [f"/{path.strip('/')}" if path.strip("/") else WHOLE_REPO_PATTERN for path in paths]
    run_git(["sparse-checkout", "set", "--no-cone", *patterns], timeout_s, cwd=dest)
    # Fetch by SHA, not branch: the branch may have moved since indexing pinned this commit.
    run_git(["fetch", "--quiet", "--depth", "1", "--filter=blob:none", "origin", sha], timeout_s, cwd=dest, env=env)
    # Checkout downloads the blobs the filter skipped, so it needs the credentials too.
    run_git(
        ["-c", "advice.detachedHead=false", "checkout", "--quiet", "--detach", "FETCH_HEAD"], timeout_s, cwd=dest, env=env
    )
