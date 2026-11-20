from enum import StrEnum


class Grouping(StrEnum):
    """How a node was made."""

    llm = "llm"  # an agent proposed it and the answer passed validation
    fallback = "fallback"  # the agent's answer failed twice for its parent, so this node is one of the parent's folders
