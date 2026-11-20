from redis import Redis

from .fields import DEDUP_KEY_FIELD, ORIGINAL_ID_FIELD


def dead_letter(client: Redis, stream: str, group: str, entry_id: str, fields: dict[str, str], dlq_stream: str) -> None:
    """Move the entry to `dlq_stream`, ack it, and free its dedup marker so the job can be queued again."""
    # One MULTI: a crash can't leave the job acked but missing from the DLQ (lost), or in the DLQ but still pending.
    with client.pipeline(transaction=True) as pipe:
        pipe.xadd(dlq_stream, {**fields, ORIGINAL_ID_FIELD: entry_id})
        pipe.xack(stream, group, entry_id)
        if DEDUP_KEY_FIELD in fields:  # entries queued before jobs carried their marker don't have it
            pipe.delete(fields[DEDUP_KEY_FIELD])
        pipe.execute()
