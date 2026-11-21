from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver

from app.deep_dive.answer import AnswerContext, DeepDiveAnswer, RenderDiagram
from app.workspace import Workspace

from .state import DeepDiveGraph


def run_graph(
    graph: DeepDiveGraph, render_diagram: RenderDiagram, key: str, workspace: Workspace, task: str, label: str
) -> DeepDiveAnswer:
    """The verified answer for the target. One thread per target (`DeepDiveBase.target_key`): a delivery that crashed mid-way resumes at the step
    that failed, and one that finished but never got its row back is reused as is, so the agents never run twice."""
    config = thread_config(key)
    context = AnswerContext(workspace, render_diagram)
    snapshot = graph.get_state(config)
    if "verified" in snapshot.values:
        final = snapshot.values
    else:
        final = graph.invoke(None if snapshot.next else {"task": task, "label": label}, config, context=context)
    return DeepDiveAnswer.model_validate(final["verified"], context=context)


def forget_thread(checkpointer: BaseCheckpointSaver, key: str) -> None:
    """Drop the target's checkpoints once its row is committed. A leftover is harmless (node ids are per snapshot)."""
    checkpointer.delete_thread(key)


def thread_config(key: str) -> RunnableConfig:
    return {"configurable": {"thread_id": key}}
