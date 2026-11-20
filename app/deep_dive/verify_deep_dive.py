import logging
from pathlib import Path

from langchain_core.language_models import BaseChatModel

from app.agent import run_agent
from app.workspace import Workspace, make_workspace_tools

from .answer import AnswerContext, DeepDiveAnswer, RenderDiagram, VerifiedAnswer
from .deep_dive_settings import DeepDiveSettings
from .humanizer_rules import BANNED_PHRASES, BANNED_WORDS
from .write_deep_dive import Slot, import_graph

PROMPTS = Path(__file__).with_name("prompts")
SYSTEM_PROMPT = (PROMPTS / "verify_system.md").read_text(encoding="utf-8").format(
    banned_words=", ".join(BANNED_WORDS), banned_phrases=", ".join(f'"{p}"' for p in BANNED_PHRASES)
)
TASK_PROMPT = (PROMPTS / "verify_task.md").read_text(encoding="utf-8")
LABEL_SUFFIX = " [verify]"

logger = logging.getLogger(__name__)


def verify_deep_dive(
    model: BaseChatModel,
    settings: DeepDiveSettings,
    slot: Slot,
    render_diagram: RenderDiagram,
    workspace: Workspace,
    task: str,
    answer: DeepDiveAnswer,
    label: str,
) -> DeepDiveAnswer:
    """A fresh agent checks every claim against the code and returns the answer with wrong claims fixed.

    Fresh context on purpose: in four review rounds the writer kept errors that rules in its own prompt targeted,
    because it can't audit a long answer in the context that produced it. Raises AgentFailed.
    """
    graph = import_graph(workspace.root, settings.import_graph_timeout_s)
    with slot():
        verified = run_agent(
            model, SYSTEM_PROMPT, TASK_PROMPT.format(repo_task=task, answer=answer.model_dump_json(indent=1)),
            make_workspace_tools(workspace, graph), VerifiedAnswer, settings.max_turns, settings.wrap_up_turns,
            label + LABEL_SUFFIX, context=AnswerContext(workspace, render_diagram),
        )
    for c in verified.corrections:
        logger.info("%s: corrected %r: %s (%s)", label, c.claim, c.problem, c.evidence)
    return verified.answer
