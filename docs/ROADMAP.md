# Roadmap

From walking skeleton to v1. Each step is small, runs on its own, and has a check that proves it works. Requirements and architecture: [DESIGN.md](../DESIGN.md). Rules: [CLAUDE.md](../CLAUDE.md).

| # | Step | Status |
|---|------|--------|
| 1 | Local infrastructure | ✅ done |
| 2 | Schema-driven data model | ✅ done |
| 3 | Gateway: `POST /repos` | ✅ done |
| 4 | Basic index worker | ✅ done |
| 5 | Areas: agentic hierarchical grouping → nodes + edges, read endpoints | ✅ done (first real run on this repo: 151 files → 54 areas, 54 agents, 0 rejected answers, 0 fallbacks, ~379k tokens, max 5 turns per agent) |
| 6 | Reliability: leases, reaper, DLQ, graceful shutdown | ✅ done |
| 7 | ~~LLM grouping~~ merged into step 5 | — |
| 8 | Deep dives | code done; needs a real run through the gateway and MinIO |
| 9 | Fairness | deferred past v1: needs multi-user |
| 10 | Agent sandbox | ✅ done (all 6 probes pass in the real container); the end-to-end run waits on a pullable MinIO image (the pinned tag is gone from Docker Hub and quay.io) |
| 11 | Frontend: add repo, map, drill into areas, deep dive (`frontend/`, React + Vite + React Flow) | ✅ done (served at `/`, screenshots checked); deep dive page unverified until MinIO runs |

**v1 is done when:** you add a repo URL, get a named map of its areas, expand any node, and generate a deep dive on it. A crashed worker loses no job, and agents can't write files or reach the network.

## How each step runs
1. **Plan:** a planning agent turns the step below into a file-by-file plan (signatures, tests, doc changes, risks). No code.
2. **Review the plan:** Claude checks it against CLAUDE.md and DESIGN.md and fixes it; the user resolves any open decisions.
3. **Build:** a dev agent writes the code and a test agent writes the tests, in parallel, from the same plan. Claude runs the tests and loops until they pass.
4. **Review:** a reviewer agent checks correctness, safety, the CLAUDE.md rules, and whether every line is needed. Findings are fixed or explicitly accepted.
5. **Docs:** DESIGN.md and `docs/interview/` are updated to the current state, and this table's status changes.

Never without asking: applying migrations to the dev database (`alembic upgrade`), or starting long-running services.

## Decisions
Pending until the user confirms. The recommendation is used if the step starts without an answer.

| Step | Decision | Recommendation | Status |
|---|---|---|---|
| 4 | Test database | separate `dd_test` DB, Alembic-migrated per test session, truncated between tests | confirmed |
| 4 | Worker concurrency | sync, scale with processes | confirmed |
| 5 | `/map` shape and depth | whole tree as `{nodes, edges}` | confirmed |
| 5 | What a node is | an area: name, description, `paths` (files or folder prefixes, each must exist; overlap allowed) | confirmed |
| 5 | Tree links | `contains` edge rows; no `parent_id`; partial unique index = at most one parent | confirmed |
| 5 | LLM access | in-house gateway; contract = messages + tools + optional response schema -> message with tool calls; wrapped as a custom LangChain chat model (`GatewayChatModel`) | confirmed |
| 5 | Grouping method | agentic: an agent per node explores with read-only tools; our code starts one subagent per returned area, in parallel | confirmed |
| 5 | Analysis libraries | griffe (`outline`), grimp (`imports`, in a subprocess), networkx (`clusters`); Python only for now | confirmed |
| 5 | Safety budget | `max_turns` 15 + 3 wrap-up turns, from the first run (max 5 turns); per-agent logging keeps it honest | confirmed |
| 5 | Contract failure after one retry | directory grouping for that node only, marked `grouping = fallback` | confirmed |
| 6 | Lease / max deliveries | 60 s / 3 | confirmed |
| 6 | Fencing token | none: every final write is insert-once, so the unique key is the fence; no migration | confirmed |
| 8 | Deep-dive addressing | one per node: `POST/GET /nodes/{id}/deep-dive` | confirmed |
| 8 | Output contract | `DeepDiveAnswer`: sections of paragraph / callout / code-excerpt / diagram (Kroki) / SVG-figure blocks, one visual per non-summary section, + optional tech stack; rendered to HTML by our template | confirmed |
| 8 | Where the page lives | S3-compatible bucket (MinIO locally), key `sha256(html).html`; row = node_id + object_key | confirmed |
| 8 | Workflow engine | LangGraph write -> verify graph with Postgres checkpoints, thread per node; `run_agent` inside each node | confirmed |
| 8 | Writing style | Hello Interview structure + humanizer rules; mechanical tells enforced by the validator | confirmed |
| 8 | Redis cache for deep dives | skip in v1; the Postgres row + bucket object are the cache | confirmed |
| 9 | User identity | `X-User-Id` header, untrusted, `TODO` real auth | deferred with step 9 |
| 9 | Fairness scope | deep dives only | deferred with step 9 |
| 10 | Network policy | deny by default: internal network + Squid egress proxy allowing HTTPS to the git hosts only (the LLM goes through the gateway) | confirmed |
| 10 | Isolation level | one hardened container per worker type, same image; no gVisor/Firecracker in v1 (no repo code runs) | confirmed |

---

## Step 4: Basic index worker
**Goal:** read a job → validate it with `RepoCreate` → skip if the repo already has a SHA → shallow-clone → insert the row with `commit_sha` (`ON CONFLICT (url) DO NOTHING`) → `XACK`. The status stays `indexing` until step 5.

| Layer | File | Responsibility |
|---|---|---|
| Wrapper | `app/git/run.py` | run git safely: `GIT_TERMINAL_PROMPT=0`, timeout, no system config |
| | `app/git/shallow_clone.py` | `git clone --depth 1 --single-branch -- <url> <dir>` → SHA. The checkout lives in a `TemporaryDirectory`, which also removes git's read-only pack files on Windows |
| | `app/queue/consumer.py` | `ensure_group`, `read_one`, `ack`; client injected |
| Domain | `app/indexing/index_repo.py` | skip if done → clone → insert; one session per job |
| | `app/indexing/worker.py` | loop; `python -m app.indexing.worker` |

**Tests:** git wrapper against a local repo in a temp dir; `index_repo` with an injected fake clone (no network).
**Done when:** a POSTed repo appears in `repos` with its `commit_sha`, and the stream entry is acknowledged.

## Step 5: Areas -> nodes + edges, read endpoints
**Goal:** checkout -> agentic hierarchical grouping -> `nodes` + `contains` edges; `GET /repos`, `GET /repos/{id}/map`, `GET /nodes/{id}`. The user types the agent machinery; Claude specifies each file.

| Layer | File | Responsibility |
|---|---|---|
| Wrapper | `app/git/list_files.py` | `git ls-files -z` ✅ |
| | `app/llm/gateway_contract/` (one model per file) | Pydantic request/response models of the gateway's `POST /v1/chat` ✅ |
| | `app/llm/gateway_chat_model/` | `GatewayChatModel(BaseChatModel)`: `to_contract`, `from_contract` (raises `GatewayAnswerError` on cut-off/refused answers), `tool_specs`, `bind_tools`, `with_structured_output` via `response_schema` ✅ |
| Service | `app/gateway/`, `Dockerfile.gateway`, compose `gateway` | the AI gateway itself: contract -> Anthropic Messages API (caching, refusal fallbacks), only holder of the API key ✅ |
| | `app/agent/run_agent.py` | send -> run tool calls -> send results -> until the answer validates (one retry with the error fed back) or `max_turns`; logs turns/tool calls/tokens/duration; tools are LangChain `StructuredTool`s ✅ |
| | `app/workspace/` | `Workspace` (confinement: `..`, absolute paths, symlinks, scope) + one file per tool: `tree`, `manifests`, `clusters`, `imports`, `outline`, `grep`, `read_file`; import graph built by grimp in an isolated subprocess ✅ |
| Schema | `app/models/node.py` + `grouping.py`, `tree_node.py`, `node_with_children.py`, `repo_map.py` | `NodeBase` (name, description, paths, grouping) -> `Node` (`CHECK cardinality(paths) > 0`) / `NodeRead`. **Migration `18c664749c48`:** drop `parent_id`, `depth`; add `grouping`; the CHECK is added by hand (autogenerate doesn't see CHECKs) ✅ |
| | `app/models/edge.py` | `kind` (`contains`), partial unique index on `target_id` for `contains`. **Migration** |
| Domain | `app/indexing/file_filters.py`, `code_files.py` | drop non-code paths ✅ |
| | `app/indexing/area_draft.py`, `submit_areas.py` | the answer schema; validated with the agent's `Workspace` as context: paths exist and are in scope, names unique and not blank, no area holds the whole scope ✅ |
| | `app/indexing/prompts/explore_system.md`, `explore_task.md` | the prompts (data) ✅ |
| | `app/indexing/directory_fallback.py` | a node's children = its immediate subfolders, `grouping = fallback` ✅ |
| | `app/indexing/explore.py`, `explore_settings.py` | top agent -> level-by-level parallel agents per area; per-node fallback; each agent run holds a slot ✅ |
| | `app/queue/semaphore_slot.py` + `semaphore_acquire.lua`, `semaphore_renew.lua` | Redis counting semaphore with leases + heartbeat: at most 3 agents at once across all workers ✅ |
| | `app/indexing/save_areas.py` | insert nodes + `contains` edges in the caller's transaction ✅ |
| | `app/indexing/index_repo.py`, `worker.py`, `make_explore.py` | clone -> explore (checkout kept until exploring ends) -> save, repo row in the same transaction; `make_explore` binds `GatewayChatModel`, settings and agent slots to `app.config` ✅ |
| | `app/indexing/index_local.py` | index a local folder without the queue (snapshot into a one-commit repo) ✅ |
| API | `app/db/session.py` | FastAPI session dependency ✅ |
| | `app/api/routes/repos.py` | `GET /repos` (indexed only), `GET /repos/{id}/map` -> `{nodes, edges}` ✅ |
| | `app/api/routes/nodes.py` | `GET /nodes/{id}` with children (via `contains` edges) ✅ |

**Tests:** contract round trip with a fake gateway (httpx mock transport); agent loop with a fake chat model; path confinement (`../`, symlinks, outside scope); explore: valid answer, invalid-then-fixed, invalid twice -> fallback node; API over saved nodes + edges. No real LLM calls in tests.
**Done when:** a real repo's map shows meaningful, nested areas, every saved path exists, and invalid LLM output never reaches the database.

## Step 6: Reliability
**Goal:** jobs survive worker crashes, poison jobs stop retrying, zombie workers can't overwrite newer work, a deploy doesn't kill a running job.

| Layer | File | Responsibility |
|---|---|---|
| Wrapper | `app/queue/fields.py`, `enqueue_once.py` | every job carries its `dedup_key` ✅ |
| | `app/queue/lease.py` + `lease_renew.lua` | heartbeat every lease/3; renews only while this consumer owns the entry ✅ |
| | `app/queue/reclaim.py` | `XAUTOCLAIM` the oldest job idle past the lease, with its delivery count ✅ |
| | `app/queue/dead_letter.py` | DLQ `XADD` + `XACK` + `DEL` dedup marker in one `MULTI` ✅ |
| | `app/queue/work_loop.py`, `work_loop_settings.py` | the shared loop: reclaim or read → dead-letter or run under a lease → ack; stops on an `Event` ✅ |
| Domain | `app/config.py` | `JOB_LEASE_S`, `JOB_MAX_DELIVERIES` ✅ |
| | `app/indexing/worker.py`, `app/deep_dive/worker.py` (+ `streams.py`) | `handle(fields)` passed to `work_loop`; SIGTERM/SIGINT → stop; `dead:index`, `dead:deep_dive` ✅ |

**Tests:** lease keeps the entry fresh and never takes back a reclaimed one; reclaim skips fresh entries and returns the delivery count; dead-letter moves, acks and frees the marker; the loop acks a success, dead-letters a poison job after `max_deliveries`, and stops on request.
**Done when:** a worker killed mid-job has its job finished by another; after N failures the job is in the DLQ and the repo can be re-added; a zombie's late write changes nothing (insert-once).

## Step 8: Deep dives
**Goal:** `POST /nodes/{id}/deep-dive` → sparse clone of the node's paths → agent → typed answer → HTML in a bucket → row in Postgres.

| Layer | File | Responsibility |
|---|---|---|
| Wrapper | `app/git/sparse_clone.py` | `--filter=blob:none`, fetch the pinned SHA, non-cone `sparse-checkout set <paths>` ✅ |
| | `app/storage/` | `ensure_bucket`, `put_object`, `get_object` on an injected `Minio` client ✅ |
| | `docker-compose.yml` | MinIO service ✅ |
| Schema | `app/models/deep_dive.py` | `DeepDiveBase` (node_id, unique) → `DeepDiveCreate` (job payload) / `DeepDive` (object_key, created_at) / `DeepDiveRead`. **Migration** ✅ |
| Domain | `app/deep_dive/answer/` | `DeepDiveAnswer` contract, one class per file; `Prose` type runs the humanizer check ✅ |
| | `app/deep_dive/humanizer_rules.py` | data: banned dashes, words, phrases ✅ |
| | `app/deep_dive/prompts/` | system prompt (Hello Interview structure, tech stack, humanizer rules) and task template ✅ |
| | `app/deep_dive/templates/deep_dive.html.j2`, `render_html.py` | autoescaped page; code excerpts copied from the checkout ✅ |
| | `app/deep_dive/write_deep_dive.py`, `make_write.py` | `run_agent` over the workspace tools, inside a shared agent slot ✅ |
| | `app/deep_dive/store_html.py`, `read_html.py` | content-addressed upload, read back ✅ |
| | `app/deep_dive/generate_deep_dive.py` | skip if done → clone → write → render → upload → insert ✅ |
| | `app/deep_dive/worker.py` | `python -m app.deep_dive.worker` ✅ |
| API | `app/api/routes/deep_dives.py` | POST → 202, GET metadata, GET html (CSP header) ✅ |

**Tests:** answer validation (dashes, banned words, excerpt bounds and scope); renderer escaping, excerpts and tech stack; sparse clone of a non-tip SHA; storage round trip (needs MinIO, skipped otherwise); generate with fakes (row, idempotency, breadcrumb); routes (queued once, 404 until written, CSP).
**Done when:** a deep dive is generated for a real node, its page renders in the browser, and a repeated job does nothing. Still open: sandbox (step 10).

## Step 9: Fairness (after v1, once there is multi-user)
With a single user there is no one to be unfair to, so this waits for user identity. The plan below is kept for then.

**Goal:** a user with 100 queued deep dives doesn't delay a user with 1.

| Layer | File | Responsibility |
|---|---|---|
| Wrapper | `app/queue/fair/enqueue.lua` | `XADD` to the user's stream + add the user to the `active_users` ring, atomically |
| | `app/queue/fair/next_job.lua` | rotate the ring (`LMOVE`) → read that user's stream → drop the user if empty, atomically |
| | `app/queue/fair/concurrency.lua` | per-user cap; counter with TTL so crashed workers don't leak slots |
| Domain | `app/deep_dive/worker.py` | fair reader; the reaper scans every user's stream |
| API | `app/api/user.py` | user identity dependency |

**Done when:** with user A at 100 jobs and user B at 1, B's job runs within the first two picks, and the per-user cap holds under concurrent workers.

## Step 10: Agent sandbox
**Goal:** untrusted repo content and the agent run with least privilege.

| File | Responsibility |
|---|---|
| `Dockerfile.worker` | one image for both workers: non-root, only Python + git (no git-lfs) + the app; `GIT_ALLOW_PROTOCOL=https` ✅ |
| `egress/squid.conf` | proxy rules: HTTPS tunnels to the git hosts only, no cache ✅ |
| `docker-compose.yml` | `x-worker` block shared by `index-worker` and `deep-dive-worker`: `read_only`, tmpfs `/tmp`, `cap_drop: ALL`, `no-new-privileges`, memory/CPU/pid limits, `sandbox` network only; `internal` network `sandbox`; `egress` proxy service ✅ |
| `app/git/run.py` | no change: system/global config is already ignored, clone doesn't recurse submodules, and https-only lives in the image because the tests clone `file://` ✅ |

**Tests:** proxy host list equals `ALLOWED_HOSTS`; opt-in probes in the real container (`SANDBOX_TESTS=1`): writes only to `/tmp`, not root and can't become root, the proxy denies other hosts, no direct route out, GitHub reachable, `git://` refused.
**Done when:** inside the container, writes outside tmpfs fail, privileged actions fail, and disallowed network access fails. ✅

## After v1
Expand-on-demand for deeper levels · import graph as a grouping signal · per-node grouping cache · SSE progress · edges endpoints · real auth + multi-user, then fairness (step 9) · re-indexing as versioned snapshots · tree-sitter import parsing · Redis cache for hot reads.
