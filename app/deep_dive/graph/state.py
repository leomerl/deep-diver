from typing import TypedDict

from langgraph.graph.state import CompiledStateGraph

from app.deep_dive.answer import AnswerContext

type AnswerJson = dict[str, object]  # a DeepDiveAnswer as `model_dump(mode="json")`


class DeepDiveState(TypedDict, total=False):
    """What the checkpointer saves between nodes.

    Answers are stored as JSON, not as models: rebuilding a `Diagram` needs the live AnswerContext (checkout + Kroki),
    which a checkpoint can't hold. Whoever reads an answer back validates it again with the current context.
    """
    task: str
    label: str
    draft: AnswerJson
    verified: AnswerJson


type DeepDiveGraph = CompiledStateGraph[DeepDiveState, AnswerContext, DeepDiveState, DeepDiveState]
