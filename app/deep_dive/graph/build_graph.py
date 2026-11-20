import logging
from collections.abc import Callable

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from app.agent import AgentFailed
from app.deep_dive.answer import AnswerContext, DeepDiveAnswer
from app.workspace import Workspace

from .state import DeepDiveGraph, DeepDiveState

type WriteStep = Callable[[Workspace, str, str], DeepDiveAnswer]  # (workspace, task, label)
type VerifyStep = Callable[[Workspace, str, DeepDiveAnswer, str], DeepDiveAnswer]  # (workspace, task, draft, label)

WRITE = "write"
VERIFY = "verify"

logger = logging.getLogger(__name__)


def build_graph(write: WriteStep, verify: VerifyStep, checkpointer: BaseCheckpointSaver) -> DeepDiveGraph:
    """write -> verify, with a checkpoint after each. Both are agent runs: the only expensive steps, so the only
    ones worth never repeating. Render, upload and insert stay outside; they're cheap and need per-job resources."""

    def write_node(state: DeepDiveState, runtime: Runtime[AnswerContext]) -> DeepDiveState:
        answer = write(runtime.context.workspace, state["task"], state["label"])
        return {"draft": answer.model_dump(mode="json")}

    def verify_node(state: DeepDiveState, runtime: Runtime[AnswerContext]) -> DeepDiveState:
        context = runtime.context
        draft = DeepDiveAnswer.model_validate(state["draft"], context=context)
        try:
            answer = verify(context.workspace, state["task"], draft, state["label"])
        except AgentFailed:
            # The draft already passed the validator; a verifier that can't produce a valid answer shouldn't throw
            # away a good page. Ship the draft unverified and say so.
            logger.warning("%s: verification failed, keeping the unverified draft", state["label"], exc_info=True)
            answer = draft
        return {"verified": answer.model_dump(mode="json")}

    return (
        StateGraph(DeepDiveState, context_schema=AnswerContext)
        .add_node(WRITE, write_node)
        .add_node(VERIFY, verify_node)
        .add_edge(START, WRITE)
        .add_edge(WRITE, VERIFY)
        .add_edge(VERIFY, END)
        .compile(checkpointer=checkpointer)
    )
