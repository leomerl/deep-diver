import threading
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Self

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.indexing.explore import explore_repo
from app.indexing.explore_settings import ExploreSettings
from app.models import Grouping, TreeNode

FILES = ["README.md", "app/auth/login.py", "app/auth/session.py", "app/billing/pay/card.py", "app/billing/refund/undo.py"]
SETTINGS = ExploreSettings(max_turns=5, wrap_up_turns=1, parallel_agents=2, import_graph_timeout_s=30)


class ByScopeModel(BaseChatModel):
    """Fake gateway model: answers each agent from a script picked by the scope named in its task.

    Agents run in parallel threads, so replies are looked up by scope, never by call order.
    """

    script: dict[str, list[AIMessage]]
    lock: threading.Lock = threading.Lock()

    @property
    def _llm_type(self) -> str:
        return "by-scope"

    def bind_tools(self, tools: object, **kwargs: Any) -> Self:  # Any: BaseChatModel's signature
        return self

    def _generate(self, messages: list[BaseMessage], stop: object = None, run_manager: object = None, **kwargs: Any) -> ChatResult:  # Any: BaseChatModel's signature
        scope = messages[1].text.split("Your scope (the only paths you can see): ")[1].splitlines()[0]
        with self.lock:
            reply = self.script[scope].pop(0)
        return ChatResult(generations=[ChatGeneration(message=reply)])


def _submit(call_id: str, *areas: tuple[str, str]) -> AIMessage:
    payload = [{"name": name, "description": f"{name} code.", "paths": [path]} for name, path in areas]
    return AIMessage("", tool_calls=[{"name": "SubmitAreas", "args": {"areas": payload}, "id": call_id}])


def _shape(nodes: list[TreeNode]) -> list[tuple[str, list[str], Grouping, list[tuple]]]:
    return [(n.name, n.paths, n.grouping, _shape(n.children)) for n in nodes]


def test_top_agent_then_one_agent_per_area_with_per_node_fallback(tmp_path: Path) -> None:
    model = ByScopeModel(script={
        "the whole repository": [_submit("t1", ("App", "app"))],
        "app": [_submit("a1", ("Auth", "app/auth"), ("Billing", "app/billing"))],
        "app/auth": [_submit("x1")],  # an empty list: Auth is a leaf
        # Billing's agent answers with a path that doesn't exist, twice: only Billing falls back.
        "app/billing": [_submit("b1", ("Pay", "app/payments")), _submit("b2", ("Pay", "app/payments"))],
    })

    tree = explore_repo(model, tmp_path, FILES, "shop", SETTINGS, nullcontext)

    assert _shape(tree) == [("App", ["app"], Grouping.llm, [
        ("Auth", ["app/auth"], Grouping.llm, []),
        # Its children are its folders, marked fallback. They hold one file each, so no agent splits them.
        ("Billing", ["app/billing"], Grouping.llm, [
            ("pay", ["app/billing/pay"], Grouping.fallback, []),
            ("refund", ["app/billing/refund"], Grouping.fallback, []),
        ]),
    ])]


def test_single_file_areas_are_not_split(tmp_path: Path) -> None:
    model = ByScopeModel(script={"the whole repository": [_submit("t1", ("Readme", "README.md"))]})

    assert _shape(explore_repo(model, tmp_path, FILES, "shop", SETTINGS, nullcontext)) == [
        ("Readme", ["README.md"], Grouping.llm, []),
    ]
