from dataclasses import dataclass


@dataclass(frozen=True)
class ExploreSettings:
    max_turns: int  # a runaway ceiling, not a tuned budget: real numbers come from the per-agent logs
    wrap_up_turns: int  # extra turns after the "wrap up now" message
    parallel_agents: int  # sibling areas explored at once; bounded by what the gateway can serve
    import_graph_timeout_s: float
