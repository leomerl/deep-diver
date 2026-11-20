from pathlib import Path

from redis import Redis

from .fields import DEDUP_KEY_FIELD

_SCRIPT = Path(__file__).with_suffix(".lua").read_text()


def enqueue_once(client: Redis, dedup_key: str, stream: str, fields: dict[str, str]) -> bool:
    """Append `fields` to `stream` unless `dedup_key` exists. Returns False for a duplicate."""
    args = [item for pair in {**fields, DEDUP_KEY_FIELD: dedup_key}.items() for item in pair]
    # register_script runs via EVALSHA and re-sends the source only if Redis lost it (NOSCRIPT)
    return bool(client.register_script(_SCRIPT)(keys=[dedup_key, stream], args=args))
