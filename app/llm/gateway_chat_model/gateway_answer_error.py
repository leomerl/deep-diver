class GatewayAnswerError(Exception):
    """The gateway answered, but the answer can't be used (cut off, refused, wrong shape).

    Separate from HTTP errors on purpose: callers may fall back on a bad answer, but an unreachable
    gateway must fail the job so it's retried later, not produce fallback output everywhere.
    """
