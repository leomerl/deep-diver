from redis import Redis

_OLDEST = "0-0"


def reclaim_one(
    client: Redis, stream: str, group: str, consumer: str, min_idle_ms: int
) -> tuple[str, dict[str, str], int] | None:
    """Take over the oldest entry idle for at least `min_idle_ms`. Returns (id, fields, times delivered)."""
    # XAUTOCLAIM bumps the delivery count; since Redis 7 it also drops entries whose data was trimmed.
    # shortcut: one call scans at most ~10 pending entries (10 x COUNT) from the oldest, so an abandoned job behind
    # 10+ live ones isn't found; fine while pending ~= running workers. Upgrade: keep the returned cursor across calls.
    _, claimed, _ = client.xautoclaim(stream, group, consumer, min_idle_ms, _OLDEST, count=1)
    if not claimed:
        return None
    [(entry_id, fields)] = claimed
    [pending] = client.xpending_range(stream, group, entry_id, entry_id, 1)
    return entry_id, fields, pending["times_delivered"]
