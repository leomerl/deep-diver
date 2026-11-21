import os

import redis
from minio import Minio
from sqlmodel import create_engine

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://dd:dd@localhost:5432/dd")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# Must outlast the workers' blocking reads (XREADGROUP BLOCK); redis-py 8's default of 5 s equals our 5 s block,
# so an idle read timed out and crashed the worker.
REDIS_SOCKET_TIMEOUT_S = float(os.getenv("REDIS_SOCKET_TIMEOUT_S", "15"))
LLM_MODEL = os.getenv("LLM_MODEL", "claude-opus-5-5")
# The agent runtimes this process may run (app.agent.AgentRuntime names, comma-separated; parsed by make_runner).
# The dashboard setting picks one of them per agent. agent_sdk needs the Claude Code login of a developer's host, so
# compose keeps the default and its workers fall back to the gateway whatever the dashboard says.
AGENT_RUNTIMES = os.getenv("AGENT_RUNTIMES", "gateway")
# The deep dive fact-checker; separate so a cheaper writer can be paired with a stronger verifier.
DEEP_DIVE_VERIFIER_MODEL = os.getenv("DEEP_DIVE_VERIFIER_MODEL", LLM_MODEL)
# Off by default: in review it added ~1 point (83 -> 84) for ~$0.40 more per deep dive.
DEEP_DIVE_VERIFY = os.getenv("DEEP_DIVE_VERIFY", "false") == "true"
LLM_GATEWAY_URL = os.getenv("LLM_GATEWAY_URL", "http://localhost:8080")
LLM_GATEWAY_KEY = os.getenv("LLM_GATEWAY_KEY", "")  # empty: the gateway needs no key
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "16000"))
LLM_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "600"))  # one agent turn can think for minutes
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "localhost:9000")  # host:port, no scheme
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "dd-minio")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "dd-minio-secret")
S3_SECURE = os.getenv("S3_SECURE", "false") == "true"  # TLS; true for anything that isn't local
DEEP_DIVE_BUCKET = os.getenv("DEEP_DIVE_BUCKET", "deep-dives")
KROKI_URL = os.getenv("KROKI_URL", "http://localhost:8001")
KROKI_TIMEOUT_S = float(os.getenv("KROKI_TIMEOUT_S", "60"))  # Mermaid starts a headless browser per render
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")  # empty: login is disabled, public repos still work
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
GITHUB_TIMEOUT_S = float(os.getenv("GITHUB_TIMEOUT_S", "15"))
# Signs the session cookie and encrypts stored GitHub tokens. Changing it logs everyone out and orphans their tokens.
SECRET_KEY = os.getenv("SECRET_KEY", "")
SESSION_MAX_AGE_S = int(os.getenv("SESSION_MAX_AGE_S", str(30 * 24 * 3600)))
GIT_LS_REMOTE_TIMEOUT_S = float(os.getenv("GIT_LS_REMOTE_TIMEOUT_S", "15"))  # POST /repos blocks on this check
JOB_LEASE_S = float(os.getenv("JOB_LEASE_S", "60"))  # renewed while a job runs; a crashed worker's job waits this long
JOB_MAX_DELIVERIES = int(os.getenv("JOB_MAX_DELIVERIES", "3"))  # then the job is dead-lettered

engine = create_engine(DATABASE_URL)
rds = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=REDIS_SOCKET_TIMEOUT_S)
s3 = Minio(S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY, secure=S3_SECURE)
