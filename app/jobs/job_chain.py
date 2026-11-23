from collections.abc import Sequence

from app.models import ChainStep, JobEventRead, JobRead, StepStatus
from app.queue import JobEventKind, JobState

# A queued job seen as one link of its parent's chain.
STATE_AS_STEP = {
    JobState.queued: StepStatus.waiting,
    JobState.running: StepStatus.running,
    JobState.retrying: StepStatus.failed,
    JobState.dead: StepStatus.failed,
    JobState.done: StepStatus.passed,
}


def step_chain(steps: Sequence[str], events: list[JobEventRead], state: JobState) -> list[ChainStep]:
    """Each checkpointed step's status. A step passed if a worker reported it on any try: a retry resumes after it."""
    passed = {e.detail for e in events if e.kind == JobEventKind.step}
    current = next((step for step in steps if step not in passed), None)

    def status(step: str) -> StepStatus:
        if step in passed:
            return StepStatus.passed
        if state == JobState.done:
            return StepStatus.skipped
        if step != current:
            return StepStatus.waiting
        if state == JobState.running:
            return StepStatus.running
        return StepStatus.waiting if state == JobState.queued else StepStatus.failed  # retrying or dead: it raised

    return [ChainStep(name=step, status=status(step)) for step in steps]


def follow_up_step(name: str, follow_up: JobRead | None, parent: JobState) -> ChainStep:
    """The link for a job the parent queues when it finishes. Not there yet: waiting while the parent can still
    queue it; skipped once the parent is done without one (a page from before notebooks, or one past the list)."""
    if follow_up is not None:
        return ChainStep(name=name, status=STATE_AS_STEP[follow_up.state])
    return ChainStep(name=name, status=StepStatus.skipped if parent in (JobState.done, JobState.dead) else StepStatus.waiting)
