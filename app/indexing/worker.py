"""Index worker: python -m app.indexing.worker"""
import logging
import os
import signal
import socket
import threading
from functools import partial

from sqlmodel import Session

from app.auth import git_env
from app.config import JOB_LEASE_S, JOB_MAX_DELIVERIES, engine, rds
from app.git import list_files, shallow_clone
from app.indexing.index_repo import index_repo
from app.indexing.make_explore import make_explore
from app.indexing.streams import INDEX_DEAD_STREAM, INDEX_GROUP, INDEX_STREAM, PAYLOAD_FIELD
from app.jobs import record_job_event
from app.models import IndexJob
from app.queue import ReportStep, WorkLoopSettings, ensure_group, work_loop

CLONE_TIMEOUT_S = 300
GIT_TIMEOUT_S = 30  # local commands on an existing checkout
READ_BLOCK_MS = 5000

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    consumer = f"{socket.gethostname()}-{os.getpid()}"  # unique per process, so pending jobs show who took them
    ls = partial(list_files, timeout_s=GIT_TIMEOUT_S)
    explore = make_explore()

    def handle(fields: dict[str, str], report_step: ReportStep) -> None:  # one step: nothing to report
        job = IndexJob.model_validate_json(fields[PAYLOAD_FIELD])
        with Session(engine) as session:
            clone = partial(shallow_clone, timeout_s=CLONE_TIMEOUT_S, env=git_env(session, job.url, job.user_id))
            index_repo(session, job, clone, ls, explore)
        logger.info("indexed %s", job.url)

    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())  # finish the current job, then exit
    settings = WorkLoopSettings(
        stream=INDEX_STREAM,
        group=INDEX_GROUP,
        dlq_stream=INDEX_DEAD_STREAM,
        lease_s=JOB_LEASE_S,
        max_deliveries=JOB_MAX_DELIVERIES,
        block_ms=READ_BLOCK_MS,
    )
    ensure_group(rds, INDEX_STREAM, INDEX_GROUP)
    logger.info("worker %s reading %s", consumer, INDEX_STREAM)
    observe = partial(record_job_event, engine, INDEX_STREAM, consumer)
    work_loop(rds, settings, consumer, handle, stop, observe)
    logger.info("worker %s stopped", consumer)


if __name__ == "__main__":
    main()
