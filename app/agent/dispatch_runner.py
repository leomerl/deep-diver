import logging
from collections.abc import Callable, Mapping, Sequence

from langchain_core.tools import BaseTool
from pydantic import BaseModel

from .agent_runner import AgentRunner
from .agent_runtime import AgentRuntime

logger = logging.getLogger(__name__)


def dispatch_runner(runners: Mapping[AgentRuntime, AgentRunner], selected: Callable[[], AgentRuntime]) -> AgentRunner:
    """A runner that asks `selected` which runtime to use on every call, so the choice changes without a restart.

    A selected runtime this process lacks falls back to the gateway with a warning: failing the job would dead-letter
    it over a deployment mismatch (a compose worker has no Claude Code login) and lose the work.
    """

    def run[T: BaseModel](
        system: str, task: str, tools: Sequence[BaseTool], answer: type[T], max_turns: int,
        wrap_up_turns: int, label: str, context: object | None = None,
    ) -> T:
        wanted = selected()
        runner = runners.get(wanted)
        if runner is None:
            logger.warning("agent %s: runtime %s is not available in this process, using %s", label, wanted, AgentRuntime.gateway)
            runner = runners[AgentRuntime.gateway]
        return runner(system, task, tools, answer, max_turns, wrap_up_turns, label, context)

    return run
