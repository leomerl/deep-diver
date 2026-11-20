DEEP_DIVE_STREAM = "jobs:deep_dive"
DEEP_DIVE_GROUP = "deep_divers"
DEEP_DIVE_DEAD_STREAM = "dead:deep_dive"  # jobs that failed JOB_MAX_DELIVERIES times, kept for inspection
PAYLOAD_FIELD = "payload"  # one JSON field holding DeepDiveCreate
NODE_DEDUP_PREFIX = "dedup:deep_dive:"  # + node id: a node is queued at most once
