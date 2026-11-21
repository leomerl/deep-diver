from collections.abc import Mapping

from .run import run_git


def ls_remote(url: str, timeout_s: float, env: Mapping[str, str] | None = None) -> str:
    """The default branch's HEAD commit SHA. Fails fast if the remote can't be read (missing, private, unreachable);
    raises like run_git."""
    # HEAD only: the default branch's one ref is enough to prove access, and the answer stays small.
    # --exit-code: an empty repo reports "no refs" as a failure instead of succeeding with no output.
    return run_git(["ls-remote", "--exit-code", "--", url, "HEAD"], timeout_s, env=env).split()[0]  # "<sha>	HEAD"
