from functools import partial

from app.agent import make_runner
from app.config import LLM_MODEL, rds
from app.indexing.explore import explore_repo
from app.indexing.explore_settings import ExploreSettings
from app.indexing.index_repo import Explore
from app.indexing.streams import AGENT_SLOTS_KEY
from app.queue import semaphore_slot
from app.settings import get_agent_runtime

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
    """The explorer bound to app.config: the agent runtimes (picked per agent by the dashboard setting), the settings
    and the shared agent slots."""
    slot = partial(semaphore_slot, rds, AGENT_SLOTS_KEY, AGENT_SLOTS, AGENT_LEASE_S, AGENT_POLL_S)
    runtime = partial(get_agent_runtime, rds)
    return partial(explore_repo, make_runner(LLM_MODEL, runtime), settings=EXPLORE_SETTINGS, slot=slot)
