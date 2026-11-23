from pathlib import Path

from app.agent import AgentRunner
from app.workspace import Workspace, make_workspace_tools

from .answer import (
    ALLOWED_HINT, MAX_CELL_LINES, MAX_CELLS, MIN_CELLS, TARGET_CELL_LINES, AnswerContext, NotebookAnswer, RenderDiagram,
)
from .deep_dive_settings import DeepDiveSettings
from .humanizer_rules import BANNED_PHRASES, BANNED_WORDS
from .write_deep_dive import Slot, import_graph

PROMPTS = Path(__file__).with_name("prompts")
# Filled from the constants the validator checks, like the writer's prompt.
SYSTEM_PROMPT = (PROMPTS / "notebook_system.md").read_text(encoding="utf-8").format(
    banned_words=", ".join(BANNED_WORDS), banned_phrases=", ".join(f'"{p}"' for p in BANNED_PHRASES),
    min_cells=MIN_CELLS, max_cells=MAX_CELLS, target_lines=TARGET_CELL_LINES, max_lines=MAX_CELL_LINES, allowed=ALLOWED_HINT,
)
TASK_PROMPT = (PROMPTS / "notebook_task.md").read_text(encoding="utf-8")
LABEL_SUFFIX = " [notebook]"


def write_notebook(
    run: AgentRunner,
    settings: DeepDiveSettings,
    slot: Slot,
    render_diagram: RenderDiagram,
    workspace: Workspace,
    task: str,
    page: str,
    label: str,
) -> NotebookAnswer:
    """A fresh agent turns the saved page (`page_text`) into runnable demos, reading the code each cell rebuilds.

    It gets the page so the notebook follows its sections instead of picking its own topics.
    Raises AgentFailed.
    """
    graph = import_graph(workspace.root, settings.import_graph_timeout_s)
    with slot():
        return run(
            SYSTEM_PROMPT, TASK_PROMPT.format(repo_task=task, page=page),
            make_workspace_tools(workspace, graph), NotebookAnswer, settings.max_turns, settings.wrap_up_turns,
            label + LABEL_SUFFIX, context=AnswerContext(workspace, render_diagram),
        )
