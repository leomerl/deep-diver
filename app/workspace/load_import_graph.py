import subprocess
import sys
from pathlib import Path

from .import_graph import ImportGraph

SCRIPT = Path(__file__).with_name("import_graph_script.py")


def load_import_graph(root: Path, timeout_s: float) -> ImportGraph:
    """Build the checkout's import graph in an isolated Python process (see import_graph_script.py).

    Raises CalledProcessError (e.g. a file grimp can't parse) or TimeoutExpired; the caller decides what to do.
    """
    # -I: ignore PYTHONPATH and the user site, and don't put the script's folder (our `app`) on sys.path.
    result = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), str(root)], capture_output=True, text=True, timeout=timeout_s, check=True
    )
    return ImportGraph.model_validate_json(result.stdout)
