# Decisions

The current state, grouped by area. Each entry covers **What** / **Why** / **Rejected** / **Failure modes** / **At scale**.

---

## Local infrastructure
Files: `docker-compose.yml`, `pyproject.toml`

**What:** Postgres 17 and Redis 7 in Docker Compose, with named volumes and healthchecks. Redis runs with `--appendonly yes --appendfsync everysec --maxmemory-policy noeviction`. The app runs on the host with `uv run`.

**Why:**
- The infrastructure matches production engines exactly (no SQLite for dev). Compose makes it one command.
- AOF `everysec`: Redis holds queue state, so it must survive a restart. At most about 1 s of writes can be lost.
- `noeviction`: queue keys must never be silently dropped. Failing loudly beats losing jobs.
- Healthchecks: "started" is not "ready". Tooling waits with `--wait`.

**Rejected:**
- *The API in Compose:* slower inner loop. Only the workers run in Compose, because the sandbox needs containers (see Agent sandbox).
- *RDB snapshots only:* minutes of lost jobs on a crash.
- *`allkeys-lru`:* would evict queue state under memory pressure.

**Failure modes:** host ports 5432 or 6379 already in use means compose won't start (change the mapping). The `dd`/`dd` credentials are dev-only.

**At scale:** managed Postgres and Redis, with Redis replication and failover. A replica can lose acknowledged writes on failover (replication is async), which is one reason Postgres stays the source of truth.

---

## Schema-driven data model
Files: `app/models/*`, `app/config.py`, `migrations/`, `alembic.ini`

**What:**
- Tables are SQLModel classes, one entity per file. `app/models/__init__.py` re-exports them, so `import app.models` registers every table.
- Alembic **generates** migrations from `SQLModel.metadata`. `migrations/env.py` gets the database URL from `app/config.py`.
- `script.py.mako` imports `sqlmodel`, because generated files reference `sqlmodel.sql.sqltypes.AutoString`.

**Why:**
- **One source of truth:** the model *is* the schema, the API contract and the validation. Changing a field is one edit, and the migration follows.
- **Base / Table / Read pattern:** API schemas inherit the table's fields, so there's no duplication and no drift.
- Reviewable migrations: generated files are code in git, applied in order, with `alembic check` as a drift guard.
- One file per entity: small diffs, clear ownership, and easy to find.

**Specific choices:**
| Choice | Why | Cost |
|---|---|---|
| `status` stored as VARCHAR (`native_enum=False`) | adding a status needs no `ALTER TYPE` | **no database-level CHECK**: only Pydantic guards values |
| `paths TEXT[]` on nodes (prefixes, overlap allowed) | read with the node; feeds the sparse clone directly | "who covers file X?" needs a GIN index later |
| Tree as `contains` edges (no `parent_id`) | one relationship table; `/map` is `{nodes, edges}` | children = a join, top level = an anti-join; whole-subtree reads need a recursive CTE |
| `snapshot_id` index | serves `GET /repos/{id}/map` | slightly slower node inserts |
| `UNIQUE (url)` | "one URL = one repo", enforced even under races | URL must be normalized before insert |
| Timestamps set in Python | simple with SQLModel | raw SQL bypasses them (see stack.md → SQLModel) |
| `INTEGER` ids | default; plenty for repos | nodes may need `BIGINT` at huge scale |

**Rejected:**
- *Raw `schema.sql` + psycopg:* the schema, API types and validation would be three separate copies that drift.
- *Plain SQLAlchemy + separate Pydantic DTOs:* every field written twice.
- *Django ORM / Tortoise / Piccolo:* Django drags in a framework; the others are less standard than SQLAlchemy and Alembic.
- *`create_all()` at startup:* no history, no reviews, no way to alter existing tables.

**Failure modes:** autogenerate turning a rename into drop + add (data loss) is mitigated by reviewing every migration. Two deploys running `upgrade` at once: run migrations as one release step, never on app start in every replica.

---

## Gateway: `POST /repos`
Files: `app/api/`, `app/indexing/`, `app/queue/`, `app/repo_url/`, `RepoCreate` in `app/models/repo.py`

**What:**
- The body is validated by `RepoCreate`, whose `url` validator normalizes the URL. An invalid URL gets a 422.
- Then one Lua script does `SET NX dedup:repo:{url}` and, only if that's new, `XADD jobs:index payload=<RepoCreate JSON>`.
- The response is always `202 {url}`, even for a duplicate. If Redis is down: `503`.

**Why:**
- **Gateway writes only to Redis:** one atomic write means no dual write. If the gateway also inserted a Postgres row, a crash between the two writes would leave a row with no job, or a job with no row.
- **Lua for atomicity:** without it, a crash between `SET NX` and `XADD` leaves a marker with no job, and that repo can never be added again.
- **Idempotent POST:** clients and proxies retry. The same URL any number of times gives one job. 202 for duplicates too, so a retry looks exactly like the first call.
- **Normalization before dedup:** `GitHub.com/a/b.git/` and `github.com/a/b` must be one key, or dedup and `UNIQUE (url)` are useless.
- **One schema everywhere:** `RepoCreate` is the request body, the response, and the job payload. The worker re-validates the payload with the same class: queue payloads are untrusted input too.
- **Payload as one JSON field:** the job can gain fields (for example `user_id` for fairness) without changing the stream layout.
- **Layers:** `app/queue/enqueue_once` is generic (Redis client injected, no repo knowledge). `app/indexing/enqueue` binds it to key names and `app.config`. The wrapper is reusable for deep-dive jobs.
- **Allowlist (security):** the worker will run `git clone` on this string. https-only blocks `file://` and `ssh://`. Rejecting anything not shaped like a URL blocks `--upload-pack=…` option injection. The host allowlist blocks SSRF to internal hosts and cloud metadata (`169.254.169.254`). Unusual input is rejected, not repaired.

**Rejected:**
- *Return a repo id in the 202:* needs a Postgres write in the gateway (dual write). The client finds the repo in `GET /repos` once it's indexed.
- *`MULTI`/`EXEC` instead of Lua:* a transaction can't branch ("XADD only if the SET succeeded"); Lua can.
- *Separate `SET NX` then `XADD` calls:* not atomic (see above).
- *Dedup with a Postgres unique constraint only:* the gateway would have to touch Postgres.
- *`async def` handler:* the Redis client is sync and would block the event loop.

**Failure modes:**
- Redis down → 503 with nothing written, so a retry is safe.
- Redis crash within about 1 s of a 202 (AOF `everysec`) can lose the job *and* the marker together, so the client can simply re-add.
- The dedup marker has no TTL, so it lives forever. It's deleted only when a job is dead-lettered (see Reliability). Removing a repo will need to delete it too.

**Known gaps:** GitHub paths are case-insensitive, but only the host is lowercased, so `Owner/Repo` and `owner/repo` are two repos (`TODO [INDEXING:LOW]`). There's no rate limit on POST yet.

**At scale:** under Redis Cluster, the dedup key and the stream need the same hash tag (`{index}`) so the script's keys share a slot. One stream for everything becomes per-user streams for fairness.

---

## Edges (node cross-links)
File: `app/models/edge.py`

**What:** a directed `source_id → target_id` (foreign keys to `nodes`, cascade), an optional `label`, `UNIQUE (source_id, target_id)` and `CHECK (source_id <> target_id)`. No endpoint uses it yet.

**Why:**
- **Containment as edges:** the tree is `kind = contains` rows. A partial unique index on `target_id WHERE kind = 'contains'` keeps "at most one parent". Neither this nor a `parent_id` column prevents cycles (`A.parent = B, B.parent = A` satisfies a foreign key); v1 is safe because only the indexer writes the tree, top-down, in one transaction, and never changes it (DESIGN §4).
- The unique pair makes edge creation idempotent, and its index also serves outgoing lookups (leftmost prefix).

**Known gaps:** an edge can link nodes from two different repos (cross-repo edges are out of scope, but the database doesn't forbid them). Edges may later need to point at deep dives as well as nodes; that's decided when edges get an endpoint.

---

## Reliability: leases, reaper, DLQ
Files: `app/queue/` (`lease.py` + `lease_renew.lua`, `reclaim.py`, `dead_letter.py`, `work_loop.py`), both `worker.py`

**What:** one loop shared by both workers. Reclaim the oldest job idle past the 60 s lease (`XAUTOCLAIM`), else read a new one. Over 3 deliveries: dead-letter it. Otherwise run it while a heartbeat renews the lease every 20 s, and `XACK` only after it succeeds. SIGTERM finishes the current job, then exits.

**Why:**
- **Short lease + heartbeat:** a crashed worker's job comes back within a minute, and a live one can run for hours (index jobs take minutes).
- **Ownership-checked renewal (Lua: `XPENDING` then `XCLAIM … JUSTID`):** a worker that stalled past its lease can't steal back a job the reaper gave away. `JUSTID` doesn't bump the delivery count.
- **Reaper inside the loop:** no extra process. Abandoned jobs go before new ones.
- **The unique key is the fence:** every final write is insert-once, so a zombie's late write does nothing. No `attempt` column, no migration.
- **Job carries its `dedup_key`:** the queue layer frees the marker without parsing a possibly broken payload, and without knowing about repos or nodes.
- **DLQ in one `MULTI`:** `XADD` dead stream + `XACK` + `DEL` marker, all or nothing.

**Rejected:**
- *Fencing token on repos:* there's no row to fence while indexing runs, and insert-once writes never overwrite.
- *Writing a `failed` repo row:* the next attempt's `ON CONFLICT` insert would hit it and drop its tree without an error.
- *A separate reaper process:* one more thing to deploy and monitor, for the same `XAUTOCLAIM` call.
- *A lease sized to the longest job:* a crash would block that job for as long.
- *Retry with explicit backoff timers:* the lease idle time already spaces retries a minute apart.

**Failure modes:**
- A stall past the lease → the job runs twice (costs LLM money, not data); logged.
- Redis down during a renewal → retried each tick; the lease outlasts a short blip.
- Orchestrator kills the worker before the job ends → recovered after one lease.

**Known gaps:** each reclaim scans only about 10 pending entries from the oldest (`shortcut:` in `reclaim.py`). There's no DLQ replay tooling. `RepoStatus.failed` is unused.

**At scale:** keep the `XAUTOCLAIM` cursor across calls. Under Redis Cluster, give each stream, its DLQ and its markers one hash tag. Per-user streams (step 9) mean the reaper has to scan every user's stream.

---

## Deep dive visuals
Files: `app/kroki/*`, `app/deep_dive/answer/{answer_context,diagram,svg_figure}.py`, `docker-compose.yml` (`kroki`, `kroki-mermaid`)

**What:** two more block types in `DeepDiveAnswer`. `Diagram` is Mermaid or Graphviz text; its validator renders it to SVG through a self-hosted Kroki and keeps the SVG on the block (a `PrivateAttr`, so it's not in the schema the model sees). `SvgFigure` is SVG the model draws itself, for what a layout engine can't draw. The template embeds both as `<img src="data:image/svg+xml;base64,...">`.

**Why:**
- The page runs no scripts (`default-src 'none'`), so Mermaid can't render in the browser; it has to become SVG before the page is stored.
- Rendering during validation turns a syntax error into an ordinary rejection the agent fixes in its retry.
- `<img>` makes any SVG inert: no scripts, no external loads, no DOM. The CSP didn't change.
- Mermaid for sequences, state and ER; Graphviz for dependency graphs with many nodes (better layout). Kroki serves both with one call.

**Rejected:**
- *mermaid-cli in the worker:* Node plus headless Chrome in every Python worker image.
- *mermaid.ink or another public renderer:* repo content leaves the machine.
- *Graphviz only:* no sequence diagrams; faking them with invisible edges fails often.
- *Generated images:* expensive, unverifiable, usually wrong in the details.
- *Inline `<svg>` in the page:* would pick up dark-mode colors, but puts model-written markup in the document.

**Failure modes:** Kroki down → `httpx` error propagates, the job fails and is redelivered, DLQ after 3. Diagram syntax error → rejection; two rejections → `AgentFailed`. The figure stays white in dark mode because both renderers draw for a light background. Mermaid renders start a headless browser each, so `KROKI_TIMEOUT_S` is 60 s.

**At scale:** Kroki is stateless, so it scales horizontally behind one URL. Rendered SVGs could be cached by `sha256(language + source)` since the same source always gives the same SVG.

---

## Frontend
Files: `frontend/` (`src/api.ts`, `scopeView.ts`, `layout.ts`, `MapCanvas.tsx`, `Breadcrumb.tsx`, `AreaNode.tsx`, `DeepDivePanel.tsx`, `tests/scopeView.test.ts`), `app/api/main.py`

**What:** a React + TypeScript app built with Vite. React Flow draws the map one scope per screen: the scope card (repo or area) on the left, its children in a column on the right, a breadcrumb floating over the canvas. Clicking an area with children makes it the scope: its card keeps its React Flow id, so a CSS transition on the node transform slides it into the parent slot while the new children and edges fade in and `setCenter(…, {duration})` eases the camera onto the scope card (zoom unchanged). `prefers-reduced-motion` turns all of it off. `npm run types` dumps `app.openapi()` and `openapi-typescript` turns it into `src/schema.d.ts`, the only place API shapes exist on the client. Dev: Vite proxies `/repos` and `/nodes` to uvicorn. Prod: FastAPI mounts `frontend/dist` at `/` after the routers, only if the folder exists.

**Why:**
- Generated types: CLAUDE.md forbids a second copy of a shape; Python and TS can't share code, so the OpenAPI spec is the bridge. `tsc` fails the build when a field a component uses has moved.
- Proxy, not CORS: one origin in the browser means no preflight, no credential flags, and the deep dive CSP behaves as in production.
- Client-side scope: `/map` is fetched once per repo (immutable snapshot); `scopeView` derives the trail (ancestors via `contains` edges) and the children of the current scope. One request, instant navigation. The scope resets via `key={repo.id}` (remount), not an effect.
- One scope per screen, not the whole tree: a repo has 10+ top-level areas and 50+ areas in total; drawn at once they shrink to unreadable cards. A star (parent + children) always fits, and it needs no layout engine, so dagre was removed.
- Polling with a 15-minute give-up: the API has no job endpoints, and a dead-lettered job never produces a row.
- `<iframe sandbox="">`: says from the embedding side what the page's CSP says from inside.

**Rejected:**
- *Static HTML + nested `<details>` served by FastAPI:* smaller, but `{nodes, edges}` was chosen for canvas libraries and `relates` cross-links don't fit a nested list.
- *`CORSMiddleware`:* a second origin and per-environment config for nothing.
- *`GET /nodes/{id}` per click:* a round trip per drill-down for data already on the client.
- *Whole tree on one canvas with dagre:* the first version; everything was tiny and the first expand made it wider. Replaced by one scope per screen.
- *Component tests:* only `scopeView` has logic that can be wrong on its own; the rest is wiring.

**Failure modes:** a repo that dead-letters is invisible (`GET /repos` lists indexed only), so the UI says "still indexing" until the cap. `schema.d.ts` must be regenerated by hand after a model change. npm 10 needs `--legacy-peer-deps` to install vitest. Vitest fails with "failed to find the current suite" when the shell's drive letter is lowercase (`c:\…`).

**At scale:** polling `GET /repos` returns the whole list every tick; the fix is job endpoints plus SSE (DESIGN §10 covers the connection cost). A scope with hundreds of direct children would need a grid or virtualisation; today the deepest column is a dozen cards. The bundle is one 530 kB chunk (React Flow); code-splitting the canvas is the first optimisation.

---

## Agent sandbox
Files: `Dockerfile.worker`, `docker-compose.yml` (`x-worker`, `sandbox`, `egress`), `egress/squid.conf`, `tests/test_egress_allowlist.py`, `tests/test_sandbox.py`

**What:**
- Both workers run from one image as a non-root user. Compose runs them with a read-only root filesystem, a 1 GB tmpfs at `/tmp`, `cap_drop: ALL`, `no-new-privileges` and memory/CPU/pid limits.
- Git may only speak https (`GIT_ALLOW_PROTOCOL` in the image). git-lfs isn't installed. `run_git` already ignores system and global git config.
- The workers sit only on the `internal` network `sandbox`, together with Postgres, Redis, MinIO, the gateway and Kroki. Their one way out is a Squid proxy that allows HTTPS tunnels to github.com, gitlab.com and bitbucket.org.

**Why:**
- The workers clone strangers' repos and let an agent read them. Every layer above (URL allowlist, read-only tools, answer validation) can have a bug, so the process itself gets least privilege.
- Deny by default: the worker needs the internet only for `git clone`. The LLM goes through the gateway, so the worker holds no key and has no route to the provider.
- https-only lives in the image, not in `run_git`, because the tests clone `file://` repos.

**Rejected:**
- *Split containers (a networked fetcher, an offline agent, a shared volume):* stronger, but every job needs a handoff between containers. Worth it once something runs repo code.
- *gVisor / Firecracker:* a kernel boundary for code execution; nothing executes repo code today.
- *No network rule in v1:* misses v1's "agents can't reach the network".
- *Generating squid.conf from `allowed_hosts.py`:* a build step for three lines; a test keeps them equal instead.

**Failure modes:** a repo bigger than the tmpfs fails the clone with "no space", retries and goes to the DLQ. A git host that redirects to another domain is blocked by the proxy (the GitHub probe would catch it). The proxy down means every clone fails and is retried. Leaking file contents through the agent's answer is still possible; `code_files` drops secrets first.

**At scale:** Kubernetes NetworkPolicy plus an egress gateway instead of the internal network and Squid; a pod `securityContext` and a memory `emptyDir` instead of the compose flags. Once repo code runs (tests, builds), a gVisor runtime class or microVMs per job.

---

## Deep dive workflow (LangGraph)
Files: `app/deep_dive/graph/*`, `app/deep_dive/make_write.py`, `app/deep_dive/worker.py`

**What:** `write -> verify` as a two-node `StateGraph` with `PostgresSaver`, thread id = node id. State: task, label, draft, verified (answers as JSON). `run_graph` resumes an unfinished thread, reuses a finished one, else starts; `forget_thread` deletes it after the row commits. Render, upload and insert stay outside the graph.

**Why:**
- The agents are the only expensive steps (~220 s and ~80 s, 300k tokens together on itsdangerous); anything failing after them redid both on redelivery.
- Already the planned point for LangGraph ("when a second expensive step needs checkpoints"); the verifier is that step.
- Resume semantics come from the library and were checked on the installed version before writing: a node failure keeps the previous checkpoint and `next` names the failed node; `invoke(None)` resumes there; fresh input restarts.

**Rejected:**
- *Hand-rolled JSON checkpoint in the bucket:* same size, but no inspection or resume tooling, and a second thing to get right.
- *Whole pipeline in the graph (render, upload, insert as nodes):* they're cheap, and they need the per-job checkout and DB session, which don't belong in state.
- *Pydantic answers in state:* can't be rebuilt without the live context (Kroki, checkout).

**Failure modes:** a leftover thread after a failed `forget` is harmless (node ids are per snapshot) and gets cleaned on the next no-op redelivery. The checkpointer tables are created by `setup()`, outside Alembic: a schema reset must drop them too. The checkpointer's connection is not thread-safe; the worker processes jobs one at a time.

**At scale:** checkpoints add one row write per node per job; negligible next to the agent cost. The thread could key on `(node_id, prompt version)` if prompts change between deliveries.

---

## Agent runtime (Claude Agent SDK as a second loop)
Files: `app/agent/agent_runner.py`, `app/agent/make_runner.py`, `app/agent/run_agent_sdk.py`, `app/agent_sdk/*`

**What:** the three agents call an `AgentRunner` instead of a chat model: system prompt, task, tools, answer schema, turn budget in; a validated answer or `AgentFailed` out. The dashboard's Settings page picks the runtime; it lives in Redis (`settings:agent_runtime`) and every worker reads it when an agent starts. `make_runner` builds each runtime the process's `AGENT_RUNTIMES` allows and `dispatch_runner` picks per call. `gateway` is our own loop on the in-house gateway. `agent_sdk` is the Claude Agent SDK, Claude Code as a library: it spawns the bundled binary, runs the tool loop itself, calls our workspace tools as in-process MCP tools and returns JSON in the answer schema. Follow-ups (rejection, nudge, wrap-up) resume the SDK session.

**Why:**
- The developer pays for a Claude Code subscription; on their own host the binary uses that login, so local indexing and deep dives run without the API key.
- One seam: all three agents already went through one function with one signature, so a second runtime is one Protocol and one factory, and callers don't change.
- A real A/B between a hand-built loop and a vendor harness, with the same log line shape plus the SDK's cost estimate.
- The SDK keeps thinking across turns, which the gateway contract drops.

**Rejected:**
- *The SDK behind the gateway's `/v1/chat`:* the SDK never hands a tool call back; it executes tools itself, and the worker holds the checkout. It replaces the loop, not the model.
- *The SDK inside the Docker workers (with a key-swapping `/v1/messages` proxy in the gateway):* only useful for API-key billing, which the gateway already does; it would put a binary and a key path into the sandbox for no gain.
- *Mounting the Claude Code login into containers, or proxying it through the gateway:* Anthropic does not allow offering claude.ai login in a product; the login stays a host-only developer convenience.
- *A fake SDK message stream for unit tests:* it would test my assumptions about the SDK, not the SDK. The pure tool conversion has unit tests; the run has a live Haiku check.
- *A per-job runtime field in the queue payload:* the choice is "which bill do I want right now", not a property of a repo or a node; one global setting matches how it's used and keeps the job schemas and the API bodies unchanged.
- *A Postgres settings table:* durable, but one operational toggle would cost a model, a migration and a session per read. Redis already holds the agent slots and the dedup keys with the same lifetime; a missing key is a safe default.
- *Failing a job whose runtime this process can't run:* a compose worker would dead-letter every job while the dashboard says `agent_sdk`. It warns and uses the gateway instead; the mismatch is a deployment fact, not a data problem.
- *Parsing `AGENT_RUNTIMES` into the enum inside `app.config`:* `app.config` importing `app.agent` while `app.agent.make_runner` imports `app.config` is a cycle; the string is parsed once at startup in `make_runner`, where a typo still fails before any job runs.

**Failure modes:** a Docker index worker and a host worker on the same stream both take jobs, so with the setting on `agent_sdk` the Docker one still bills the API key; stop the compose workers when everything should run on the login. The setting is read per agent, so a change mid-index switches the remaining agents, not the running one. The CLI reports "out of turns" as an error result that arrives as an exception or as the last message depending on its exit code, so both paths feed one handler. Without `strict_mcp_config` and empty `setting_sources`, the binary behaves like interactive Claude Code: a first run sent 400k tokens of the developer's MCP tool schemas, and a repo's project settings could run hooks. The binary validates the answer schema as strict JSON Schema, and Pydantic emits OpenAPI's `discriminator` for tagged unions: the first live deep dive died before its first turn until the wrapper stripped that key (the index schema has no unions, so unit tests and the index run never saw it). Resume needs the session files under the Claude config dir. A follow-up gets a fixed `wrap_up_turns`, where `run_agent` gives the remaining budget. The login's rate limits are shared with interactive Claude Code; a full Opus index can exhaust a window. `total_cost_usd` is a client-side estimate.

**At scale:** production stays on `gateway`: one key holder, one egress rule set, per-turn control. The SDK runtime could run on an API key by setting `ANTHROPIC_API_KEY` in `AgentSdkSettings.env`, but then it only trades our loop for a binary per agent. Concurrency is bounded by the Redis agent slots in both runtimes.

## Focused deep dives and the whole-repo deep dive
Files: `app/deep_dive/answer/deep_dive_answer.py`, `app/deep_dive/prompts/write_system.md`, `app/deep_dive/prompts/write_repo_task.md`, `app/models/deep_dive.py`, `app/api/routes/repo_deep_dives.py`, `migrations/versions/2e428da2a463_root_deep_dives.py`

**What:** the writer first names the three things a reader must leave with (core mechanism, main trade-off, main failure) and writes at most five sections around them. A validator caps the page at 5 sections, 900 words of paragraph and callout text, 4 callouts, 3 tech stack entries and 5 questions. Separately, a deep dive can now be about the whole repo: `deep_dives.node_id` is nullable, every row carries `repo_id`, and `/repos/{id}/deep-dive` mirrors the node routes. Clicking the repo card on the map opens it.

**Why:**
- Measured before the change: 9 to 11 sections and 1,600 to 2,100 words of section prose per page, with edge cases at the same weight as the core idea. The old prompt asked for eight sections and told the model never to trade basics for findings, so it kept everything.
- A validator, not just prompt text: models drift past soft length limits, and a rejection with the word count in it is something the one retry can fix.
- Nullable `node_id` keeps "the repo row is the root" true; the root deep dive is a fact about the repo, not a fake area.

**Rejected:**
- *A hidden root `Node` row:* smaller diff (every node route works unchanged), but every tree query would have to skip it, and the check `cardinality(paths) > 0` would need a fake `""` path.
- *`snapshot_id` only on root rows, with a CHECK that exactly one of the two is set:* list queries would need a COALESCE join through the node. Setting it always makes every list a direct join.
- *A per-section word limit:* sections differ too much in honest size; one page-wide budget lets the model spend words where the area needs them.

**Failure modes:** a first draft over the budget costs the one retry; two misses fail the job like any other invalid answer. The 900-word cap is set from four sample pages, not from a run under the new prompt, so it needs checking against real output. Nothing in the database stops a row whose `snapshot_id` differs from its node's snapshot; only the API sets both, from the node. The root deep dive's quality depends on indexing's top-level descriptions, which go into its task.

**At scale:** a composite FK `(node_id, snapshot_id) → nodes(id, snapshot_id)` would make the snapshot/node pairing a database guarantee.

---

## Re-indexing: versioned snapshots
Files: `app/models/snapshot.py`, `app/indexing/index_repo.py`, `app/api/routes/repos.py`, `migrations/versions/c58189f08c6d_snapshots.py`, `frontend/src/Reindex.tsx`

**What:** a `snapshots` table (repo, commit, unique per pair) owns each tree and its deep dives. `repos.current_snapshot_id` says which one `/map` shows. `POST /repos/{id}/reindex` reads HEAD with `git ls-remote` and queues a job keyed on `url:sha`, unless HEAD is already current. The worker clones HEAD, builds the snapshot unless it exists, and moves the pointer under a fence (`head_seen_at`, read from the DB clock before cloning). `GET /deep-dives/{id}/html` reaches any page, including old snapshots' root pages.

**Why:**
- Immutable trees keep the old safety arguments (no cycles, no partial reads) and keep every old deep dive valid for its own commit.
- The unique (repo, commit) key makes a repeated job a no-op without any coordination.
- The pointer is the one overwrite in the system, so it is the one place with a fencing token.

**Rejected:**
- *Edit the tree in place:* breaks deep dives, needs a cycle guard on every edge insert, and exposes half-updated trees.
- *`commit_sha` on nodes, no table:* the database can't enforce one tree per commit.
- *Last-finisher-wins pointer (no fence):* a slow job on an older commit could roll the repo back.
- *A compare-and-set on the pointer value seen at start:* rejects a newer job whenever an older one finished first.
- *Worker wall clock for the fence:* skew between machines can reorder jobs.

**Failure modes:** a force-push back to a commit queued before is not re-queued (dedup marker exists), so the pointer stays on the newer commit; the client gives up after 15 min. Old snapshots and their trees are never deleted. Jobs queued with the old `{repo_id}` deep dive payload fail validation after the deploy and dead-letter.

**At scale:** garbage-collect snapshots no deep dive points at; a webhook could call the reindex route on push; a per-node result cache keyed on (repo, commit, paths) would let a re-index reuse agents for areas whose files didn't change.

## LLM usage tracking at the gateway
Files: `app/gateway/record_call.py`, `app/gateway/cost.py`, `app/gateway/prices.py`, `app/models/llm_call.py`, `app/llm/gateway_contract/caller.py`, `app/agent/make_runner.py`, `app/usage/report.py`, `migrations/versions/980a43208d26_llm_calls.py`

**What:** one `llm_calls` row per answered model call (model, four token counts, cost in dollars, agent label, run id), written by the gateway; a report prints spend per day and per agent label.

**Why:** $44 was spent and nothing could say on what. The only per-agent record was a stdout log line that a container rebuild deletes, and it added input and output tokens into one number, though output costs five times more.

**Rejected:**
- *Recording in the worker:* it knows the job, but every new caller would have to remember to record, and a crash mid-run loses the rows for calls already paid. The gateway is the one place every paid call passes through.
- *Passing the queue's delivery attempt down to each call:* about six signatures for the same answer that "one label, two run ids" gives.
- *Storing tokens only and pricing at report time:* prices change; the report should show what was paid.
- *Failing the request when the insert fails:* the call is already paid; an error makes the agent retry and pay again. The row is logged with every field instead.

**Failure modes:** a fallback-rescued call is priced entirely at the answering model's rates (marked `shortcut:` in `cost.py`). An answer the gateway can't convert (an unexpected stop reason) is paid but not recorded. Runs on the Claude Code login never reach the gateway.

**At scale:** a daily cap in the gateway that sums today's `cost_usd` and returns 429; per-repo attribution by adding the repo to the caller.
