from app.config import rds
from app.indexing.streams import INDEX_STREAM, PAYLOAD_FIELD, REPO_DEDUP_PREFIX
from app.models import IndexJob
from app.queue import enqueue_once


def enqueue_index_job(repo: IndexJob) -> bool:
    """Queue indexing for `repo`. Returns False if it was already added."""
    return enqueue_once(
        rds, f"{REPO_DEDUP_PREFIX}{repo.url}", INDEX_STREAM, {PAYLOAD_FIELD: repo.model_dump_json()}
    )
