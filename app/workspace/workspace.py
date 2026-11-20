from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from langchain_core.tools import ToolException

WHOLE_REPO = ""  # how a normalized path spells the repo root


@dataclass(frozen=True)
class Workspace:
    """What one agent may see: a checkout, its tracked code files, and the agent's scope inside them.

    Every tool reads through this class, so `../`, absolute paths, symlinks out of the checkout and
    paths outside the scope are rejected in one place.
    """

    root: Path
    files: frozenset[str]  # repo-relative, "/"-separated
    scope: tuple[str, ...] = ()  # path prefixes the agent may look at; empty = the whole repo

    def normalize(self, path: str) -> str:
        parts = PurePosixPath(path.replace("\\", "/")).parts
        if parts and (parts[0] == "/" or parts[0].endswith(":")):
            raise ToolException(f"{path!r}: use a path relative to the repo root")
        if ".." in parts:
            raise ToolException(f"{path!r}: '..' is not allowed")
        return "/".join(parts)

    def in_scope(self, path: str) -> bool:
        return not self.scope or any(_under(path, prefix) for prefix in self.scope)

    def files_under(self, path: str) -> list[str]:
        """Files under `path` that are in scope. Raises if the path is outside the scope or holds no files."""
        base = self.normalize(path)
        if base != WHOLE_REPO and not self.in_scope(base):
            raise ToolException(f"{path!r} is outside your scope: {', '.join(self.scope)}")
        found = sorted(f for f in self.files if _under(f, base) and self.in_scope(f))
        if not found:
            raise ToolException(f"no files under {path!r}")
        return found

    def file_path(self, path: str) -> Path:
        """The on-disk path of one tracked, in-scope file. Raises if it resolves outside the checkout."""
        name = self.normalize(path)
        if name not in self.files or not self.in_scope(name):
            raise ToolException(f"{path!r} is not a file in your scope")
        real = (self.root / name).resolve()
        # A tracked symlink can point anywhere (e.g. /etc/passwd): follow it and check where it lands.
        if not real.is_relative_to(self.root.resolve()):
            raise ToolException(f"{path!r} points outside the repository")
        return real


def _under(path: str, prefix: str) -> bool:
    return prefix == WHOLE_REPO or path == prefix or path.startswith(f"{prefix}/")
