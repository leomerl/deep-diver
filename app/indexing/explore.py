import logging
import subprocess
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager
from pathlib import Path

from app.agent import AgentFailed, AgentRunner
from app.llm.gateway_chat_model import GatewayAnswerError
from app.models import TreeNode
from app.workspace import ImportGraph, Workspace, load_import_graph, make_workspace_tools

from .directory_fallback import directory_fallback
from .explore_settings import ExploreSettings
from .submit_areas import SubmitAreas

PROMPTS = Path(__file__).with_name("prompts")
SYSTEM_PROMPT = (PROMPTS / "explore_system.md").read_text(encoding="utf-8")
TASK_PROMPT = (PROMPTS / "explore_task.md").read_text(encoding="utf-8")
WHOLE_REPO = ()
WHOLE_SCOPE = "."
WHOLE_REPO_LABEL = "the whole repository"
BREADCRUMB_SEPARATOR = " > "
MIN_FILES_TO_SPLIT = 2  # one file can't be split into areas, so no agent is spent on it

type Pending = tuple[TreeNode, tuple[str, ...]]  # a node still to split, and the names of the areas above it
type Slot = Callable[[], AbstractContextManager[None]]  # held for one whole agent run; caps agents per machine

logger = logging.getLogger(__name__)


def explore_repo(
    run: AgentRunner, root: Path, files: list[str], repo_name: str, settings: ExploreSettings, slot: Slot
) -> list[TreeNode]:
    """Map the checkout at `root` into a tree of areas: the top-level areas, each with its sub-areas filled in.

    One agent splits the whole repo; then every area is split by its own agent, one level at a time. Siblings
    run in parallel. Going level by level means no agent ever waits on another inside the thread pool.
    """
    if not files:
        return []
    graph = _import_graph(root, settings.import_graph_timeout_s)
    known = frozenset(files)

    def split(pending: Pending) -> list[TreeNode]:
        node, breadcrumb = pending
        workspace = Workspace(root=root, files=known, scope=tuple(node.paths))
        return _split(run, workspace, graph, settings, slot, repo_name, breadcrumb)

    top = _split(run, Workspace(root=root, files=known, scope=WHOLE_REPO), graph, settings, slot, repo_name, ())
    level: list[Pending] = [(node, (node.name,)) for node in top]
    with ThreadPoolExecutor(max_workers=settings.parallel_agents) as pool:
        while level:
            results = list(pool.map(split, level))
            for (node, _), children in zip(level, results, strict=True):
                node.children = children
            level = [
                (child, (*breadcrumb, child.name))
                for (_, breadcrumb), children in zip(level, results, strict=True)
                for child in children
            ]
    return top


def _split(
    run: AgentRunner,
    workspace: Workspace,
    graph: ImportGraph,
    settings: ExploreSettings,
    slot: Slot,
    repo_name: str,
    breadcrumb: tuple[str, ...],
) -> list[TreeNode]:
    if len(workspace.files_under(WHOLE_SCOPE)) < MIN_FILES_TO_SPLIT:
        return []
    label = BREADCRUMB_SEPARATOR.join((repo_name, *breadcrumb))
    task = TASK_PROMPT.format(
        repo=repo_name, area=label, scope=", ".join(workspace.scope) or WHOLE_REPO_LABEL
    )
    try:
        # The slot covers the whole run, tools included, so many agents can't overload the machine.
        with slot():
            answer = run(
                SYSTEM_PROMPT, task, make_workspace_tools(workspace, graph), SubmitAreas,
                settings.max_turns, settings.wrap_up_turns, label, context=workspace,
            )
    except (AgentFailed, GatewayAnswerError):
        # Only this node falls back. An unreachable gateway raises something else and fails the whole job.
        logger.warning("%s: falling back to directory grouping", label, exc_info=True)
        return directory_fallback(workspace)
    return [TreeNode(name=area.name, description=area.description, paths=area.paths) for area in answer.areas]


def _import_graph(root: Path, timeout_s: float) -> ImportGraph:
    # The graph only improves the agents' hints; a repo grimp can't read is still mapped, without it.
    try:
        return load_import_graph(root, timeout_s)
    except subprocess.CalledProcessError as e:
        # The traceback's last line is the exception itself (e.g. which file failed to parse); the rest is noise.
        logger.warning("no import graph: %s", (e.stderr.strip().splitlines() or ["(no error output)"])[-1])
    except subprocess.TimeoutExpired:
        logger.warning("no import graph: timed out after %ss", timeout_s)
    return ImportGraph()
