from functools import partial

import httpx
from langgraph.checkpoint.base import BaseCheckpointSaver
from pydantic import SecretStr

from app.config import (
    DEEP_DIVE_VERIFIER_MODEL, DEEP_DIVE_VERIFY, KROKI_TIMEOUT_S, KROKI_URL, LLM_GATEWAY_KEY, LLM_GATEWAY_URL,
    LLM_MAX_TOKENS, LLM_MODEL, LLM_TIMEOUT_S, rds,
)
from app.indexing.make_explore import AGENT_LEASE_S, AGENT_POLL_S, AGENT_SLOTS
from app.indexing.streams import AGENT_SLOTS_KEY
from app.kroki import render_svg
from app.llm.gateway_chat_model import GatewayChatModel
from app.queue import semaphore_slot
from app.workspace import Workspace

from .answer import DeepDiveAnswer
from .deep_dive_settings import DeepDiveSettings
from .generate_deep_dive import Write
from .graph import build_graph, run_graph
from .verify_deep_dive import verify_deep_dive
from .write_deep_dive import write_deep_dive

SETTINGS = DeepDiveSettings(
    max_turns=60,  # high on purpose: only stops runaway agents until the logs give real numbers
    wrap_up_turns=3,
    import_graph_timeout_s=120,
)


def make_write(checkpointer: BaseCheckpointSaver) -> Write:
    """The write -> verify graph bound to app.config. Both agents share indexing's agent slots (same key and limit),
    so indexing and deep dives together never run more agents than the gateway is sized for."""
    slot = partial(semaphore_slot, rds, AGENT_SLOTS_KEY, AGENT_SLOTS, AGENT_LEASE_S, AGENT_POLL_S)
    render_diagram = partial(render_svg, httpx.Client(base_url=KROKI_URL, timeout=KROKI_TIMEOUT_S))
    write = partial(write_deep_dive, _model(LLM_MODEL), SETTINGS, slot, render_diagram)
    verify = (
        partial(verify_deep_dive, _model(DEEP_DIVE_VERIFIER_MODEL), SETTINGS, slot, render_diagram)
        if DEEP_DIVE_VERIFY else _keep_draft  # same graph shape either way; the verify node then just passes through
    )
    return partial(run_graph, build_graph(write, verify, checkpointer), render_diagram)


def _keep_draft(workspace: Workspace, task: str, draft: DeepDiveAnswer, label: str) -> DeepDiveAnswer:
    return draft


def _model(name: str) -> GatewayChatModel:
    return GatewayChatModel(
        base_url=LLM_GATEWAY_URL,
        model=name,
        max_tokens=LLM_MAX_TOKENS,
        timeout_s=LLM_TIMEOUT_S,
        api_key=SecretStr(LLM_GATEWAY_KEY) if LLM_GATEWAY_KEY else None,
    )
