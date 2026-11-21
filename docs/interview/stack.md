# Tech stack, in depth

Each section covers what the technology is, how it works inside (as far as interviews go), how we use it, and its sharp edges.

---

## Docker Compose
**What:** a YAML file that describes several containers, their networks and their volumes, and starts them with one command.

**How we use it:** local infrastructure (Postgres, Redis, MinIO, the gateway, Kroki) and the two sandboxed workers. The API runs on the host with `uv run`.

**Key ideas:**
- **Named volumes** (`pgdata`, `redisdata`) are managed by Docker and outlive the containers. `docker compose down` keeps the data, and `down -v` deletes it.
- **Port mapping** `"5432:5432"` publishes a container port on the host. Inside the compose network, services reach each other by service name (`postgres:5432`), not `localhost`.
- **Healthchecks** (`pg_isready`, `redis-cli ping`) let `docker compose up --wait` return only when the services *accept connections*. "Container started" is not the same as "ready". `depends_on: condition: service_healthy` uses the same signal.
- **Internal networks** (`internal: true`) have no route to the outside. A container on one internal and one normal network is reachable from both, and its ports still publish to the host. The workers are on `sandbox` only.
- **Hardening flags:** `read_only` mounts the image's filesystem read-only; `tmpfs` adds an in-memory writable folder that disappears with the container; `cap_drop: [ALL]` removes the kernel powers even container root has; `no-new-privileges` stops setuid binaries from raising privileges; `mem_limit`, `cpus` and `pids_limit` stop one container from starving the host.
- **YAML anchors** (`x-worker: &worker`, then `<<: *worker`) share one block between services. Compose ignores top-level keys that start with `x-`.

**Sharp edges:** Compose is a dev and single-host tool. It doesn't reschedule, scale across machines or roll deploys. In production that's Kubernetes or ECS plus managed Postgres (RDS) and Redis (ElastiCache).

---

## PostgreSQL
**Role:** the source of truth. Anything that must survive lives here.

**MVCC (Multi-Version Concurrency Control):** an UPDATE writes a new row version, and readers keep seeing the old one until the writer commits. *Readers never block writers, and writers never block readers.* The cost is dead row versions, which **VACUUM** (autovacuum) cleans up.

**Constraints are our correctness backbone:**
- `UNIQUE (url)` on `repos` enforces "one URL = one repo" in the database itself, even if two workers race. The worker uses `INSERT … ON CONFLICT (url) DO UPDATE` (an upsert), which is atomic.
- **Foreign keys with `ON DELETE CASCADE`:** deleting a repo deletes its nodes, which deletes their edges. No orphans, and no cleanup code.
- `CHECK (source_id <> target_id)` on `edges` blocks self-loops.

**Indexes (B-tree):**
- A composite index is usable by its *leftmost prefix*: `(a, b)` also serves `WHERE a = ?`. `/map` filters only on `snapshot_id`, so `ix_nodes_snapshot_id` is a plain single-column index.
- `UNIQUE (source_id, target_id)` on `edges` is also an index on `source_id`, so outgoing edges need no separate index. Incoming edges need `ix_edges_target_id`.
- Every index speeds up reads and slows down writes (each one is updated on every insert). We only index known queries.

**Tree storage: an adjacency list, kept as `contains` rows in `edges` (no `parent_id` column).** Other options an interviewer might raise:
| Model | Children | Whole subtree | Moves | Why not (for now) |
|---|---|---|---|---|
| **Adjacency list** (ours) | one indexed query | recursive CTE (`WITH RECURSIVE`) | update one row | n/a |
| Materialized path / `ltree` | prefix query | prefix query | rewrite the subtree's paths | extra extension; a repo's tree is rebuilt, never moved |
| Closure table | join | join | many rows | O(n·depth) storage for no benefit here |
| Nested sets | range | range | renumber half the tree | terrible for writes |
Our access pattern is "expand one node → fetch its children", which is exactly what an adjacency list is best at.

**`paths TEXT[]` (array column) instead of a files table:** a node's paths (files or folder prefixes) are always read and written with the node, and the deep dive's sparse clone takes them as-is. There's no exactly-once rule, so there's nothing a join table would enforce.

**Types:** `TIMESTAMPTZ` stores UTC and converts on display. Always use it, never `TIMESTAMP` without a time zone. IDs are `INTEGER` with sequences (about 2.1 billion max). That's fine for repos. Nodes could reach it at huge scale, and moving to `BIGINT` is a one-line model change.

---

## Redis
**Role:** the queue (Streams), dedup markers, leases, and later a cache and rate limits. It is **not** the source of truth.

**Single-threaded command execution:** commands run one at a time, so each command is atomic. A **Lua script** (`EVAL`) also runs atomically: nothing else runs in the middle of it. That's how we'll do "set the dedup marker AND enqueue" as one step (step 3).

**Persistence: what survives a restart:**
| Mode | How | Loss window |
|---|---|---|
| RDB | periodic snapshot (fork + dump) | minutes of writes |
| AOF `always` | fsync every write | ~none, slowest |
| **AOF `everysec`** (ours) | fsync once per second | about 1 s of writes |
| AOF `no` | the OS decides when to flush | ~30 s |
*Why `everysec`:* it's Redis's default compromise. Losing about 1 s of queue writes is acceptable because clients get a 202 only after the write. The worst case is a client re-adding a repo.

**Eviction (`maxmemory-policy`):** when memory is full, Redis either drops keys (`allkeys-lru`, `volatile-lru`, and others) or returns errors (`noeviction`).
*Why `noeviction`:* an evicted stream or dedup marker is a **silently lost job** or a duplicate. An error is loud: the gateway returns 5xx and the client retries. If we later add cache keys to the same Redis, the option is `volatile-lru`, with TTLs only on cache keys, so only those can be evicted. Better still is a separate Redis for the cache.

---

**Lua scripts, in more detail:**
- `EVAL script numkeys key… arg…`. Keys are passed separately from args so Redis Cluster can check that every key lives on the same node. Our two keys (`dedup:repo:…` and `jobs:index`) would need a shared hash tag such as `{index}` under Cluster.
- `EVALSHA sha1` runs a script that's already cached, without resending its source. redis-py's `register_script` tries `EVALSHA` first and falls back to `EVAL` on `NOSCRIPT` (for example after a Redis restart).
- A script blocks the whole server while it runs, so scripts must be tiny. Ours is two commands.
- It isn't a rollback transaction: if a command fails mid-script, earlier writes stay. Ours can't half-fail in practice. For a script without flags, Redis checks memory once, at the script's first write (our `SET`). If memory is full, the `SET` fails and nothing is written; once the `SET` succeeds, the `XADD` is allowed to run.

**Streams (basics; consumer groups come with the worker):**
- An append-only log. `XADD jobs:index * payload {...}` appends an entry, and `*` means Redis assigns the ID `<ms timestamp>-<seq>`, which is monotonic.
- Unlike pub/sub, entries **persist** until trimmed, so a worker that's down misses nothing.
- Unlike a list (`LPUSH`/`BRPOP`), a popped list item is gone. With a stream, a consumer group tracks what each consumer has read but not yet acknowledged. That pending list is what makes leases and retries possible.

---

## FastAPI
**What:** an ASGI web framework built on Starlette (HTTP) and Pydantic (validation). Function signatures *are* the API contract.

**How a request flows here:** `POST /repos` with JSON → FastAPI sees the parameter `repo: RepoCreate` and validates the body with it, which runs our `url` validator → an invalid body gets a **422** with field-level errors and never reaches our code → the return type `-> RepoCreate` becomes the response schema and the OpenAPI docs (`/docs`).

**`def` vs `async def`:** our handler is a plain `def`, so FastAPI runs it in a **threadpool**. That's right because the Redis client is synchronous and would block the event loop inside an `async def`. Rule: blocking I/O → `def`; awaitable I/O (async drivers) → `async def`.

**Routers:** `APIRouter(prefix="/repos")` groups the endpoints for one resource in one file, and `main.py` only assembles them, which keeps one responsibility per file.

**Status codes we use:** `202 Accepted` (work is queued, not done), `422` (invalid input), `503` (a dependency is down, retry is safe).

---

## Pydantic (v2)
**What:** data classes with validation driven by type hints. The core is written in Rust (`pydantic-core`), so it's fast.

**Validators:** `@field_validator("url")` runs after type checking. It may transform the value (we normalize the URL) or raise `ValueError`, which becomes a `ValidationError` (a 422 in FastAPI). Validators run only on *non-table* SQLModel classes (see SQLModel below), which is why the validator sits on `RepoCreate`, not `Repo`.

**Why here:** every boundary gets a typed contract: API input and output (FastAPI uses Pydantic natively), the LLM output contract (step 7), and job payloads. Invalid data fails at the edge with a precise error, not three layers deep.

---

## SQLAlchemy (2.x)
**What:** the standard Python SQL toolkit. **Core** builds SQL expressions. **ORM** maps classes to tables and adds a `Session`, a *unit of work* that collects changes and flushes them in one transaction.

**Engine and pool:** `create_engine()` creates a connection pool. By default that's `QueuePool` with 5 connections plus 10 overflow. Connections are reused, not opened per query. In production, also watch Postgres's `max_connections`; PgBouncer helps when many processes each hold a pool.

**Driver:** `postgresql+psycopg://` means psycopg 3, the current Postgres driver (sync and async, server-side binding).

---

## SQLModel
**What:** one class that is *both* a Pydantic model and a SQLAlchemy table. Written by FastAPI's author.

**Our pattern (fields defined once):**
```
RepoBase   shared fields        → plain Pydantic
Repo       RepoBase, table=True → the DB table; migrations generated from it
RepoRead   RepoBase + id …      → API response
RepoCreate RepoBase + validator → API input, and the queue job payload
```
API schemas and tables inherit the same fields, so they can't drift.

**Sharp edges you must know:**
- **`table=True` models skip validation on construction.** `Repo(url=123)` won't raise. Validation happens on the non-table schemas (`RepoCreate`), which is why input always goes through those.
- It's a thin layer that lags SQLAlchemy. Postgres-specific types need escape hatches: `sa_type=ARRAY(String)`, `sa_type=sa.Enum(...)`, `sa_column_kwargs`.
- `default_factory` (for example `created_at`) and `onupdate` (`updated_at`) run **in Python, not in the database**. A raw-SQL insert that skips the column fails NOT NULL, and a raw-SQL update doesn't bump `updated_at`. Fix if needed: `server_default=func.now()`, plus a trigger for `updated_at`.

---

## Alembic
**What:** schema migrations for SQLAlchemy. Each migration is a Python file with `upgrade()` and `downgrade()`.

**How versions work:** each file has a `revision` and a `down_revision`, which together form a linked list (a DAG if branches are merged). The database stores the current revision in the `alembic_version` table. `upgrade head` applies every file between that revision and the newest.

**Autogenerate = a diff:** it compares `SQLModel.metadata` (our models) to the live database and writes the difference as a migration. **It's a draft, not truth.** Blind spots:
- a column **rename** looks like drop + add (data loss!) and must be fixed by hand;
- **enum value changes**, CHECK constraint changes and server defaults are partly or poorly detected;
- **data migrations** (backfills) are never generated.
So every generated file is read before it's applied. `alembic check` exits non-zero if the models and the database differ, and it belongs in CI.

**Zero-downtime migrations (common interview topic): expand → migrate → contract.** First add the new column or table (old code still works). Deploy code that writes both. Backfill. Switch reads. Only then drop the old column. Never rename or drop in the same deploy as the code change.

---

## uv
**What:** a fast Python package and project manager (Rust). `pyproject.toml` lists dependencies, and `uv.lock` pins exact versions for every transitive dependency, so every machine and CI run installs the same thing. `uv run` runs inside the project's virtual environment without activating it.

---

## Kroki
**What:** an HTTP service that turns diagram text (Graphviz, Mermaid, PlantUML and about twenty others) into SVG, PNG or PDF. `POST /{language}/svg` with the source as the body returns the image; a 400 carries the renderer's syntax error.

**How we use it:** `app/kroki/render_svg.py`, one function over an injected `httpx.Client`. The `kroki` container renders Graphviz itself; Mermaid needs a headless browser, so Kroki forwards it to the `kroki-mermaid` companion container (`KROKI_MERMAID_HOST`).

**Key ideas:**
- **Safe mode** (`KROKI_SAFE_MODE`, default `secure`) blocks renderer features that read local files, such as DOT's `image=` attribute. That matters because the source is model-written.
- **Stateless:** every request carries its whole input, so instances are interchangeable and the result is cacheable by a hash of the source.
- **Sharp edges:** Mermaid renders are slow (a browser per render) and the companion image is large. Kroki's SVGs assume a light background.

---

## React Flow
**What:** React Flow (`@xyflow/react`) is a React component that draws nodes and edges on a pannable, zoomable canvas. You give it arrays of `{id, position, data}` nodes and `{id, source, target}` edges and it handles rendering, hit-testing and viewport. It does **no** layout: positions are your job.

**How we use it:** one scope per screen. `layout.ts` places the scope card at the left and its children in a column (a star needs no layout engine; dagre was used for the whole-tree version and removed). Custom node types (`AreaNode`, `RepoNode`) render cards with a description and a child count; a `Panel` holds the breadcrumb. Dragging and connecting are off because the tree is immutable.

**Key ideas:**
- **Stable ids make animation free:** the card you click keeps its id when it becomes the scope, so React Flow updates the same DOM element's transform and a CSS `transition` slides it; new cards get a keyframe fade-in; `useReactFlow().setCenter(x, y, {duration})` eases the camera onto the scope card (which sits at the vertical middle of its children) once `useNodesInitialized()` says the new cards are measured; `fitView` runs only on first mount.
- **`nodeTypes` must be a module constant:** a new object per render makes React Flow remount every node and kills the transition.
- **Edges are first-class:** the same canvas will draw `relates` cross-links later with no model change, which a nested list can't.
- **Sharp edges:** React Flow is the bulk of the bundle (about 480 kB minified). Nodes that leave the screen are removed immediately, so there is no exit animation without extra bookkeeping.

---

## Vite + openapi-typescript
**What:** Vite is a dev server and bundler: it serves TypeScript modules natively in dev (esbuild transforms per file, no bundle step) and bundles with Rollup for production. `openapi-typescript` turns an OpenAPI 3 document into TypeScript types with no runtime code.

**How we use it:** `vite.config.ts` proxies `/repos` and `/nodes` to the API, so the browser talks to one origin. `npm run types` imports the FastAPI app in Python, prints `app.openapi()` and generates `src/schema.d.ts`; `api.ts` reads `components["schemas"]["RepoRead"]` and friends from it. `npm run build` runs `tsc --noEmit` first, so a stale schema fails the build if a used field moved.

**Key ideas:**
- **One source of truth across languages:** the spec is derived from the SQLModel classes, the types from the spec. Nothing is typed twice by hand.
- **Proxy over CORS:** CORS is a browser rule about two origins; a proxy removes the second origin instead of permitting it.
- **Sharp edges:** generation is manual. npm 10 crashes on vitest's optional peer set (`--legacy-peer-deps`). Vitest on Windows needs an uppercase drive letter in the cwd or it can't match the collected file to the executing one.

---

## LangGraph
**What:** a library for stateful, multi-step LLM workflows as graphs: nodes are functions over a shared typed state, edges fix the order, and a checkpointer saves the state after every node so a run can be resumed, inspected or replayed.

**How we use it:** `app/deep_dive/graph/`: two nodes (`write`, `verify`), state as a `TypedDict`, `PostgresSaver` for checkpoints, one thread per node id, runtime context (`AnswerContext`) passed per invocation rather than stored. Each node still calls our own `run_agent` loop; LangGraph owns the sequencing and persistence, not the tool loop.

**Key ideas:**
- **Thread:** a checkpoint lineage keyed by `thread_id`. Invoking with input appends a new turn; invoking with `None` continues the pending one.
- **Checkpoint after each node, not each LLM call:** a crash inside a node redoes that node.
- **Serialization:** state must survive a round trip through the checkpointer, so keep JSON-shaped values; objects with context-bound validators don't belong there.
- **Sharp edges:** `PostgresSaver` wants an autocommit connection and creates its own tables; the saver's connection is single-threaded.

---

## Claude Agent SDK
**What:** Claude Code as a Python library (`claude-agent-sdk`). The wheel bundles the Claude Code binary; `query()` spawns it, streams its messages back and ends with a `ResultMessage`.

**How we use it:** `app/agent_sdk/` wraps it as a second agent runtime. `run_sdk` takes a system prompt, a task, LangChain tools, an answer JSON schema and a turn budget, and returns an `SdkResult`. Workspace tools become in-process MCP tools; built-in tools, settings files and other MCP servers are switched off.

**Key ideas:**
- **In-process MCP server** (`create_sdk_mcp_server`): tools run in our Python process; the binary calls them over an in-memory transport. Tool names on the wire are `mcp__<server>__<tool>` and must appear in `allowed_tools`.
- **Structured output** (`output_format` with a JSON schema): the SDK adds a `StructuredOutput` tool and retries until the JSON matches; the parsed object is `ResultMessage.structured_output`.
- **Sessions** (`resume=session_id`): a later call continues the same conversation, thinking included. The session lives in files under the Claude config dir.
- **Isolation flags:** `tools=[]`, `setting_sources=[]`, `strict_mcp_config=True`. Without them the binary behaves like interactive Claude Code: user MCP servers, project hooks, built-in file tools.
- **Credentials:** `ANTHROPIC_API_KEY` in the binary's environment wins; otherwise the host's Claude Code login. `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` stops update checks and telemetry.

**Sharp edges:** 0.2.x, the API changes between releases. "Out of turns" is an error result that arrives as an exception or a message depending on exit code. `total_cost_usd` is an estimate from a bundled price table. Each run is a process; concurrency is bounded by our Redis agent slots, not by the SDK.
