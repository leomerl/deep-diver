"""Run as `python -I import_graph_script.py <checkout>`: prints the checkout's internal import graph as JSON.

A separate process on purpose. grimp finds packages with importlib's find_spec, which searches sys.path: in the
worker, a repo package named `app` would resolve to our own `app`. Here, with -I, the checkout is the only extra
path, and the untrusted repo stays out of the worker's memory. Standalone: it must not import anything from `app`.
"""
import json
import sys
from pathlib import Path

import grimp

SOURCE_DIRS = ("src", ".")  # the two common layouts: src/<package> and <package> at the root
INIT_FILE = "__init__.py"


def main() -> None:
    root = Path(sys.argv[1]).resolve()
    bases = [(root / d).resolve() for d in SOURCE_DIRS if (root / d).is_dir()]
    sys.path[:0] = [str(base) for base in bases]
    # Skip names already imported here (json, sys, grimp...): find_spec would return those, not the repo's.
    packages = {
        child.name: base
        for base in bases
        for child in sorted(base.iterdir())
        if (child / INIT_FILE).is_file() and child.name.isidentifier() and child.name not in sys.modules
    }
    if not packages:
        print(json.dumps({"modules": {}, "imports": {}}))
        return
    graph = grimp.build_graph(*packages, cache_dir=None)
    print(json.dumps({
        "modules": {module: _file(root, packages, module) for module in graph.modules},
        "imports": {module: sorted(graph.find_modules_directly_imported_by(module)) for module in graph.modules},
    }))


def _file(root: Path, packages: dict[str, Path], module: str) -> str:
    parts = module.split(".")
    stem = packages[parts[0]].joinpath(*parts)
    path = stem / INIT_FILE if stem.is_dir() else stem.with_suffix(".py")
    return path.relative_to(root).as_posix()


if __name__ == "__main__":
    main()
