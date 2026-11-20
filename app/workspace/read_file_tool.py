from typing import Annotated

from langchain_core.tools import BaseTool, ToolException
from pydantic import Field

from .make_tool import make_tool
from .workspace import Workspace

READ_WINDOW = 200  # lines per call; the agent pages on with start_line
MAX_LINE_CHARS = 300  # minified or generated lines would otherwise eat the context


def make_read_file_tool(workspace: Workspace) -> BaseTool:
    def read_file(
        path: Annotated[str, Field(description="File relative to the repo root.")],
        start_line: Annotated[int, Field(description="First line to show (1-based).")] = 1,
    ) -> str:
        """Read up to 200 numbered lines of one file. Use it after tree, outline or grep point you to a file."""
        try:
            lines = workspace.file_path(path).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as e:
            raise ToolException(f"can't read {path!r}: {e.strerror}") from e
        start = max(start_line, 1)
        window = lines[start - 1:start - 1 + READ_WINDOW]
        numbered = [f"{n}: {line[:MAX_LINE_CHARS]}" for n, line in enumerate(window, start)]
        return "\n".join([*numbered, f"(lines {start}-{start + len(window) - 1} of {len(lines)})"])

    return make_tool(read_file)
