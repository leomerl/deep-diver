import subprocess
from typing import Annotated

from langchain_core.tools import BaseTool, ToolException
from pydantic import Field

from app.git import run_git

from .make_tool import make_tool
from .output_limit import limit_lines
from .workspace import WHOLE_REPO, Workspace

GREP_TIMEOUT_S = 30
NO_MATCH_EXIT_CODE = 1  # git grep's "nothing found", not an error
MAX_LINE_CHARS = 200


def make_grep_tool(workspace: Workspace) -> BaseTool:
    def grep(
        pattern: Annotated[str, Field(description="Extended regular expression, as in `grep -E`.")],
        path: Annotated[str, Field(description="Folder or file to search; '.' means your whole scope.")] = ".",
    ) -> str:
        """Search the code for a regular expression. Returns `file:line: text` for each match."""
        base = workspace.normalize(path)
        workspace.files_under(path)  # rejects paths outside the scope before git runs
        pathspecs = [base] if base != WHOLE_REPO else list(workspace.scope) or ["."]
        # --literal-pathspecs: a path is never read as a glob. `-e`: a pattern starting with "-" is never a flag.
        args = ["--literal-pathspecs", "grep", "-n", "-I", "-z", "-E", "-e", pattern, "--", *pathspecs]
        try:
            out = run_git(args, GREP_TIMEOUT_S, cwd=workspace.root)
        except subprocess.CalledProcessError as e:
            if e.returncode == NO_MATCH_EXIT_CODE:
                return "no matches"
            raise ToolException(f"grep failed: {e.stderr.strip()}") from e
        except subprocess.TimeoutExpired as e:
            raise ToolException("grep timed out; narrow the path or the pattern") from e
        matches = (line.split("\0", 2) for line in out.splitlines())
        found = [f"{file}:{n}: {text.strip()[:MAX_LINE_CHARS]}" for file, n, text in matches if file in workspace.files]
        return limit_lines(found) if found else "no matches"

    return make_tool(grep)
