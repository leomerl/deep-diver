class AgentSdkError(Exception):
    """The Claude Code binary or the API behind it failed (process, connection, HTTP error).

    An unusable answer is not an error: it comes back as an SdkResult without an answer, so callers can nudge
    or fall back, while this exception fails the job so the queue retries it later.
    """
