from functools import partial

from pydantic import SecretStr

from app.config import LLM_GATEWAY_KEY, LLM_GATEWAY_URL, LLM_MAX_TOKENS, LLM_MODEL, LLM_TIMEOUT_S, rds
from app.indexing.explore import explore_repo
from app.indexing.explore_settings import ExploreSettings
from app.indexing.index_repo import Explore
from app.indexing.streams import AGENT_SLOTS_KEY
from app.llm.gateway_chat_model import GatewayChatModel
from app.queue import semaphore_slot

AGENT_SLOTS = 3  # agents running at once across every process sharing this Redis
AGENT_LEASE_S = 60  # a dead worker's slot frees itself after this
AGENT_POLL_S = 2
EXPLORE_SETTINGS = ExploreSettings(
    # First real run (151 files, 54 agents): max 5 turns, most 2-3. 3x the max still only stops runaway agents.
    max_turns=15,
    wrap_up_turns=3,
    parallel_agents=3,  # matches AGENT_SLOTS: more threads would only wait for a slot
    import_graph_timeout_s=120,
)


def make_explore() -> Explore:
    """The explorer bound to app.config: the gateway model, the settings and the shared agent slots."""
    model = GatewayChatModel(
        base_url=LLM_GATEWAY_URL,
        model=LLM_MODEL,
        max_tokens=LLM_MAX_TOKENS,
        timeout_s=LLM_TIMEOUT_S,
        api_key=SecretStr(LLM_GATEWAY_KEY) if LLM_GATEWAY_KEY else None,
    )
    slot = partial(semaphore_slot, rds, AGENT_SLOTS_KEY, AGENT_SLOTS, AGENT_LEASE_S, AGENT_POLL_S)
    return partial(explore_repo, model, settings=EXPLORE_SETTINGS, slot=slot)
