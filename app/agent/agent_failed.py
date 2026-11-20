class AgentFailed(Exception):
    """The agent ended without a valid answer: too many rejected answers, or out of turns."""
