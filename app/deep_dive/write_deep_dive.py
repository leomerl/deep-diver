import logging
import subprocess
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path

from langchain_core.language_models import BaseChatModel

from app.agent import run_agent
from app.workspace import ImportGraph, Workspace, load_import_graph, make_workspace_tools

from .answer import AnswerContext, DeepDiveAnswer, RenderDiagram
from .deep_dive_settings import DeepDiveSettings
from .humanizer_rules import BANNED_PHRASES, BANNED_WORDS

PROMPTS = Path(__file__).with_name("prompts")
# The banned lists are filled in from humanizer_rules, the same lists the validator checks: one source, no drift.
SYSTEM_PROMPT = (PROMPTS / "write_system.md").read_text(encoding="utf-8").format(
    banned_words=", ".join(BANNED_WORDS), banned_phrases=", ".join(f'"{p}"' for p in BANNED_PHRASES)
)
TASK_PROMPT = (PROMPTS / "write_task.md").read_text(encoding="utf-8")

type Slot = Callable[[], AbstractContextManager[None]]  # one of the agent slots shared with indexing

logger = logging.getLogger(__name__)


def write_deep_dive(
    model: BaseChatModel,
    settings: DeepDiveSettings,
    slot: Slot,
    render_diagram: RenderDiagram,
    workspace: Workspace,
    task: str,
    label: str,
) -> DeepDiveAnswer:
    """Run the agent over the checkout until it submits an answer that validates. Raises AgentFailed."""
    graph = import_graph(workspace.root, settings.import_graph_timeout_s)
    with slot():
        return run_agent(
            model, SYSTEM_PROMPT, task, make_workspace_tools(workspace, graph), DeepDiveAnswer,
            settings.max_turns, settings.wrap_up_turns, label, context=AnswerContext(workspace, render_diagram),
        )


def import_graph(root: Path, timeout_s: float) -> ImportGraph:
    # The graph only feeds the imports/clusters tools; without it the agent still has tree, grep and read_file.
    try:
        return load_import_graph(root, timeout_s)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        logger.warning("no import graph for %s", root, exc_info=True)
        return ImportGraph()
