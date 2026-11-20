from dataclasses import dataclass


@dataclass(frozen=True)
class WorkLoopSettings:
    stream: str
    group: str
    dlq_stream: str
    lease_s: float  # a job idle this long is presumed abandoned and handed to another worker
    max_deliveries: int  # the next delivery after this goes to the DLQ
    block_ms: int  # how long one read waits; also the longest a stop request waits when idle
