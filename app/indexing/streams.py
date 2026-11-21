INDEX_STREAM = "jobs:index"
PAYLOAD_FIELD = "payload"  # one JSON field: the job schema can grow without changing the stream layout
REPO_DEDUP_PREFIX = "dedup:repo:"  # + normalized URL + ":" + HEAD SHA; deleted only when a job is dead-lettered
INDEX_GROUP = "indexers"  # one consumer group; every index worker joins it
INDEX_DEAD_STREAM = "dead:index"  # jobs that failed JOB_MAX_DELIVERIES times, kept for inspection
AGENT_SLOTS_KEY = "slots:agents"  # sorted set of agent slot holders -> lease expiry (ms)
