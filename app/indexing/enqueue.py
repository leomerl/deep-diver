from app.config import rds
from app.indexing.streams import INDEX_STREAM, PAYLOAD_FIELD, REPO_DEDUP_PREFIX
from app.models import IndexJob
from app.queue import enqueue_once


def enqueue_index_job(repo: IndexJob, head_sha: str) -> bool:
    """Queue indexing of `repo` at `head_sha`. Returns False if that commit was already queued."""
    # Keyed on the commit: one commit's snapshot is built once, so the marker never needs freeing; a new commit
    # gets a new key, which is what lets a re-index through.
    return enqueue_once(
        rds, f"{REPO_DEDUP_PREFIX}{repo.url}:{head_sha}", INDEX_STREAM, {PAYLOAD_FIELD: repo.model_dump_json()}
    )
