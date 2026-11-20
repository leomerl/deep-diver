from redis import Redis
from redis.exceptions import ResponseError

_NEW_ENTRIES = ">"  # XREADGROUP id meaning "entries never delivered to this group"
_FROM_START = "0"  # a new group also sees entries added before it existed


def ensure_group(client: Redis, stream: str, group: str) -> None:
    """Create the consumer group (and the stream) if missing. Safe to call on every start."""
    try:
        client.xgroup_create(stream, group, id=_FROM_START, mkstream=True)
    except ResponseError as e:
        if "BUSYGROUP" not in str(e):  # BUSYGROUP = already exists; anything else is real
            raise


def read_one(
    client: Redis, stream: str, group: str, consumer: str, block_ms: int
) -> tuple[str, dict[str, str]] | None:
    """Take one new entry for this consumer, waiting up to `block_ms`. None if nothing came."""
    response = client.xreadgroup(group, consumer, {stream: _NEW_ENTRIES}, count=1, block=block_ms)
    if not response:
        return None
    [(_, [(entry_id, fields)])] = response
    return entry_id, fields


def ack(client: Redis, stream: str, group: str, entry_id: str) -> None:
    """Mark the entry done; until then it stays in the group's pending list."""
    client.xack(stream, group, entry_id)
