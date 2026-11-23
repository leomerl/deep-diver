from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver

from app.deep_dive.answer import AnswerContext, DeepDiveAnswer, RenderDiagram
from app.queue import ReportStep
from app.workspace import Workspace

from .state import DeepDiveGraph


def run_graph(
    graph: DeepDiveGraph,
    render_diagram: RenderDiagram,
    key: str,
    workspace: Workspace,
    task: str,
    label: str,
    report_step: ReportStep,
) -> DeepDiveAnswer:
    """The verified answer for the target. One thread per target (`DeepDiveBase.target_key`): a delivery that crashed mid-way resumes at the step
    that failed, and one that finished but never got its row back is reused as is, so the agents never run twice. Each node that passes is
    reported once its checkpoint is saved."""
    config = thread_config(key)
    context = AnswerContext(workspace, render_diagram)
    snapshot = graph.get_state(config)
    if "verified" not in snapshot.values:  # the last node's output: present once the thread finished
        start = None if snapshot.next else {"task": task, "label": label}
        # "sync": the checkpoint is written before the next node starts, so a reported step is one a crash keeps.
        for update in graph.stream(start, config, context=context, stream_mode="updates", durability="sync"):
            for node in update:
                report_step(node)
    final = graph.get_state(config).values
    # Re-validated against this delivery's checkout: excerpts are checked again and diagrams re-rendered.
    return DeepDiveAnswer.model_validate(final["verified"], context=context)


def forget_thread(checkpointer: BaseCheckpointSaver, key: str) -> None:
    """Drop the target's checkpoints once its row is committed. A leftover is harmless (node ids are per snapshot)."""
    checkpointer.delete_thread(key)


def thread_config(key: str) -> RunnableConfig:
    return {"configurable": {"thread_id": key}}
