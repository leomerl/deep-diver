from datetime import UTC, datetime

from app.jobs import follow_up_step, step_chain
from app.models import JobEventRead, JobRead, StepStatus
from app.queue import JobEventKind, JobState

STEPS = ("write", "verify")
NOW = datetime.now(UTC)


def _event(n: int, kind: JobEventKind, delivery: int = 1, detail: str | None = None) -> JobEventRead:
    return JobEventRead(id=n, stream="s", entry_id="1-0", kind=kind, delivery=delivery, consumer="w", detail=detail, created_at=NOW)


def _statuses(events: list[JobEventRead], state: JobState) -> list[StepStatus]:
    return [s.status for s in step_chain(STEPS, events, state)]


def test_the_step_after_the_last_passed_one_is_running() -> None:
    events = [_event(1, JobEventKind.started), _event(2, JobEventKind.step, detail="write")]
    assert _statuses(events, JobState.running) == [StepStatus.passed, StepStatus.running]


def test_a_retry_keeps_steps_passed_on_an_earlier_try_and_marks_the_one_that_raised() -> None:
    events = [_event(1, JobEventKind.started), _event(2, JobEventKind.step, detail="write"), _event(3, JobEventKind.failed, detail="Boom")]
    assert _statuses(events, JobState.retrying) == [StepStatus.passed, StepStatus.failed]
    assert _statuses(events, JobState.dead) == [StepStatus.passed, StepStatus.failed]


def test_a_queued_job_waits_and_a_done_job_without_step_events_skipped_them() -> None:
    assert _statuses([], JobState.queued) == [StepStatus.waiting, StepStatus.waiting]
    assert _statuses([_event(1, JobEventKind.done)], JobState.done) == [StepStatus.skipped, StepStatus.skipped]


def test_a_follow_up_link_takes_its_jobs_state_or_waits_for_the_parent() -> None:
    notebook = JobRead(
        stream="jobs:notebook", entry_id="2-0", label="r", state=JobState.running, queued_at=NOW, deliveries=1,
        consumer="w", chain=[], events=[],
    )
    assert follow_up_step("notebook", notebook, JobState.done).status == StepStatus.running
    assert follow_up_step("notebook", None, JobState.running).status == StepStatus.waiting  # queued when the page is saved
    assert follow_up_step("notebook", None, JobState.done).status == StepStatus.skipped
