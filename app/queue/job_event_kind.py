from enum import StrEnum


class JobEventKind(StrEnum):
    """What happened to a queued job, as the work loop saw it."""

    started = "started"  # a delivery began; a retry is a second `started` with a higher delivery
    step = "step"  # one checkpointed step of a multi-step job passed; the detail names it
    failed = "failed"  # the delivery raised; the detail is the exception, and the job stays pending for a retry
    done = "done"  # acked
    dead_lettered = "dead_lettered"  # out of deliveries, moved to the DLQ
