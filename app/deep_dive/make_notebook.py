from functools import partial

import httpx

from app.agent import make_runner
from app.config import KROKI_TIMEOUT_S, KROKI_URL, LLM_MODEL, rds
from app.indexing.make_explore import AGENT_LEASE_S, AGENT_POLL_S, AGENT_SLOTS
from app.indexing.streams import AGENT_SLOTS_KEY
from app.kroki import render_svg
from app.queue import semaphore_slot
from app.settings import get_agent_runtime

from .generate_notebook import WriteNotebook
from .make_write import SETTINGS
from .write_notebook import write_notebook


def make_notebook() -> WriteNotebook:
    """The notebook agent bound to app.config, in the same agent slots as indexing and deep dives."""
    slot = partial(semaphore_slot, rds, AGENT_SLOTS_KEY, AGENT_SLOTS, AGENT_LEASE_S, AGENT_POLL_S)
    render_diagram = partial(render_svg, httpx.Client(base_url=KROKI_URL, timeout=KROKI_TIMEOUT_S))
    runner = make_runner(LLM_MODEL, partial(get_agent_runtime, rds))
    return partial(write_notebook, runner, SETTINGS, slot, render_diagram)
