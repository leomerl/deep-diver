from dataclasses import dataclass


@dataclass(frozen=True)
class DeepDiveSettings:
    max_turns: int  # a runaway ceiling, not a tuned budget: real numbers come from the per-agent logs
    wrap_up_turns: int  # extra turns after the "wrap up now" message
    import_graph_timeout_s: float
