from collections.abc import Sequence

# Keeps one tool result from flooding the agent's context. Not a limit on the map: the agent can narrow its query.
MAX_OUTPUT_LINES = 300


def limit_lines(lines: Sequence[str]) -> str:
    if len(lines) <= MAX_OUTPUT_LINES:
        return "\n".join(lines)
    hidden = len(lines) - MAX_OUTPUT_LINES
    return "\n".join([*lines[:MAX_OUTPUT_LINES], f"... {hidden} more lines; narrow the path or the query"])
