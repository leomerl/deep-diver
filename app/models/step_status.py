from enum import StrEnum


class StepStatus(StrEnum):
    passed = "passed"
    running = "running"
    failed = "failed"  # raised on the last try; a retrying job runs it again
    waiting = "waiting"
    skipped = "skipped"  # a finished job that never ran it: reused a checkpoint, or ran before steps were recorded
