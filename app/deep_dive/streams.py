DEEP_DIVE_STREAM = "jobs:deep_dive"
DEEP_DIVE_GROUP = "deep_divers"
DEEP_DIVE_DEAD_STREAM = "dead:deep_dive"  # jobs that failed JOB_MAX_DELIVERIES times, kept for inspection
PAYLOAD_FIELD = "payload"  # one JSON field holding DeepDiveCreate
DEDUP_PREFIX = "dedup:deep_dive:"  # + DeepDiveBase.target_key: a node, or a repo root, is queued at most once
