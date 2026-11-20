from collections.abc import Collection

from pydantic import BaseModel


class ImportGraph(BaseModel):
    """Internal Python imports of one checkout. Parsed from a subprocess's output, so it's validated."""

    modules: dict[str, str] = {}  # module name -> repo-relative file
    imports: dict[str, list[str]] = {}  # module name -> modules it imports directly

    def modules_in(self, files: Collection[str]) -> set[str]:
        return {module for module, file in self.modules.items() if file in files}
