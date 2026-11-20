import os
import subprocess
from collections.abc import Mapping
from pathlib import Path

# GIT_TERMINAL_PROMPT=0: a private or missing repo fails fast instead of hanging on a credential prompt.
# No system/global config: host settings (url.insteadOf, credential helpers, hooks paths) can't change what we fetch.
_ENV = {
    **os.environ,
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
}


def run_git(args: list[str], timeout_s: float, cwd: Path | None = None, env: Mapping[str, str] | None = None) -> str:
    """Run git and return its stripped stdout. `env` adds variables (auth). Raises CalledProcessError or TimeoutExpired."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            env={**_ENV, **(env or {})},
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        # The exception's message has only the exit code; git's reason is in stderr. Notes print with the traceback.
        e.add_note(e.stderr.strip())
        raise
    return result.stdout.strip()
