# Codebase Map — Design (v1)

A platform that maps your repos into a navigable tree of code areas, and generates AI deep dives on any part of it.
Also an interview-prep exercise: every decision below has a "why" you should be able to defend.

## 1. Requirements

### Functional
- Add a repo by URL (multiple repos, each mapped and explored separately).
- Log in with GitHub, see the repos the account can read (private ones included) and pick which to index. The worker clones with that user's token.
- Index the repo → a tree of areas (areas / sub-areas), drawn top-level first; click a node to expand it.
- Click a node → generate a deep dive about that part of the code.
- (Later) connect deep dives / nodes with edges.

### Out of scope for v1
- Re-indexing / webhooks / staleness. A repo is indexed once and pinned to its commit. To refresh: remove and re-add.
- Git history in indexing (latest commit only).
- Cross-repo edges, multi-user permissions. **Single tenant:** every logged-in user sees every indexed repo, private ones included. Fine on one person's machine, not on a shared deploy.
- Fairness between users (per-user queues, round robin, per-user cap). It needs user identity, so it comes with multi-user. Until then one shared stream per job type is FIFO.
- Job/progress endpoints (deferred).

### Non-functional
- **Idempotent POSTs.** One URL = one repo; repos can't be duplicated. Always return 202 (async).
- **Reliability.** Deep dive jobs are idempotent (a finished node is skipped; the page is content-addressed). Checkpoints between steps come with the first multi-step workflow. Indexing jobs survive worker crashes (leases + reaper).
- **Security.** Repo URLs are https-only, with no credentials, port, query or fragment, and the host must be on an allowlist (`app/repo_url/allowed_hosts.py`: github.com, gitlab.com, bitbucket.org), because the worker runs `git clone` on them (SSRF, option injection). Agents are read-only, run an explicit allowlist of tools, and execute inside a container.
- **GitHub login.** OAuth App (not a GitHub App: no installation flow, no JWT signing), scope `repo`, the only scope that reads private repos. The callback's `state` must match a short-lived cookie (CSRF). The session cookie carries only a signed user id (`itsdangerous`, 30 days, HttpOnly, SameSite=Lax). The access token is stored Fernet-encrypted under `SECRET_KEY` (`users.access_token_enc`), in Postgres rather than Redis because deep dives clone again long after login. Git receives it through `GIT_CONFIG_*` environment variables as an `http.<origin>/.extraheader` Basic header, so it is scoped to the repo's host and never appears in a process listing. A job payload carries the adder's `user_id` (`IndexJob`), never the token, and a client cannot set it: `RepoCreate` is the request body, `IndexJob` the queue payload.
- **Sandbox.** Both workers run from `Dockerfile.worker` as a non-root user, with a read-only root filesystem, a 1 GB tmpfs at `/tmp` (the only writable place; checkouts live there), `cap_drop: ALL`, `no-new-privileges` and memory/CPU/pid limits (compose `x-worker`). Git may only speak https (`GIT_ALLOW_PROTOCOL` in the image); git-lfs isn't installed, and `run_git` ignores system and global git config, so a repo can't bring filters, hooks or submodules into play. Network: deny by default. The workers sit only on the `internal` compose network `sandbox`, which reaches Postgres, Redis, MinIO, the gateway and Kroki. Their one way out is the Squid proxy `egress` (`egress/squid.conf`), which allows HTTPS tunnels to the `ALLOWED_HOSTS` git hosts and nothing else; a test keeps the two lists equal. The LLM API is not on the list: workers reach it through the gateway. Probes in `tests/test_sandbox.py` (opt-in) check each rule inside the real container.
- Numbers (scale, latency, cost targets): to be set later.

## 2. Stack
- Python 3.12, uv, FastAPI, LangChain (LLM calls); LangGraph for the deep dive's write -> verify graph (Postgres checkpoints)
- Postgres (source of truth), Redis (queue, cache, coordination), S3-compatible object storage (deep dive pages; MinIO locally, via the `minio` client)
- Jinja2 (renders deep dive HTML, autoescaped)
- **Frontend** (`frontend/`): React + TypeScript on Vite; React Flow draws the map, one scope per screen (a parent card and its children in a column, so no layout engine). Its API types are generated from the OpenAPI spec (`npm run types` → `src/schema.d.ts`), so the SQLModel classes stay the one source. In dev, Vite proxies `/repos` and `/nodes` to uvicorn (one origin, no CORS); in prod FastAPI serves `frontend/dist` at `/`, mounted after the routers. Install with `npm install --legacy-peer-deps` (npm 10 crashes resolving vitest's optional peers).
- **Schema-driven:** SQLModel classes are the tables, the API schemas and the validation; Alembic autogenerates migrations from them.
- docker-compose for local dev (Postgres, Redis, MinIO, gateway, Kroki) and for the sandboxed workers (`index-worker`, `deep-dive-worker`, egress proxy)
- **LLM gateway:** an in-house HTTP service owns provider, model, keys and provider retries. The app talks to it only through `GatewayChatModel` (`app/llm/`), a custom LangChain chat model, so LangGraph and the indexer's agent loop use it like any LangChain model.
  - **Contract** (`app/llm/gateway_contract/` (one model per file), Pydantic; one source for client and gateway): `POST /v1/chat` with `{model, messages, tools, response_schema?, max_tokens}` → `{message, stop_reason, usage}`. Messages have roles `system | user | assistant | tool`; an assistant message carries `tool_calls` (`id`, `name`, `arguments`), a tool message carries `tool_call_id`.
  - Why not text in → text out: deep dives and the indexer are agents, and an agent needs structured tool calls; a text-only contract would also force parsing JSON out of free text instead of using native structured output (`response_schema`).
  - Errors: 4xx = bad request, not retried; 429/5xx/timeouts = retryable.
  - Provider limits pass through: response and tool schemas can't be recursive.
  - **The service** (`app/gateway/`, `Dockerfile.gateway`, compose service `gateway` on :8080): FastAPI on the official `anthropic` SDK. It's the only process holding `ANTHROPIC_API_KEY` (compose passes that one variable from `.env`; `.dockerignore` keeps `.env` out of the image). Optional bearer key (`GATEWAY_KEY`, compared in constant time). Per request: leading system messages → top-level `system`, later ones stay as mid-conversation system messages; all tool results of a turn go back in one user message; `response_schema` → `output_config.format` via `transform_schema`; automatic prompt caching (agents resend their whole history every turn); server-side refusal fallbacks (`fallbacks: "default"`). Errors: provider 400 → 400, 429 → 429, other provider/network errors → 502.
  - Thinking blocks are not carried by the contract, so every request replays none. Removing *all* thinking blocks keeps a conversation valid under the history check; the cost is that the model doesn't see its earlier reasoning across turns. TODO [LLM:MEDIUM] carry thinking blocks opaquely through the contract.
  - Why LangChain over the raw Anthropic SDK: one LLM stack for indexing and deep dives (LangGraph's tool binding, streaming and checkpoints assume a LangChain chat model); `with_structured_output` covers the indexing contract; switching provider (e.g. a local model for privacy) is one line; learning LangChain is a goal of the project.
  - Accepted costs: new Anthropic features reach the SDK first; one more layer makes errors and retries harder to trace; more dependencies to keep updated.

## 3. Architecture

```
FE ──► API gateway ──► Redis Streams ──► clone + index service ──► git (shallow clone), Postgres, LLM
                  │
                  └──► Redis Streams ──► deep dive service ──► git (checkout at the pinned commit), LLM, bucket (HTML), Postgres (row)
```

- Both flows are **async**.
- Index and deep dive are separate services: different lifecycles and scaling profiles (indexing is long and heavy; deep dives are shorter and will grow into multi-step workflows, e.g. video/image generation).
- **Code is not persisted in the system.** Each deep dive checks out the repo at the pinned commit into a temp dir, which is deleted after the run. Agents read from the local dir (filesystem tools work better than object storage).
- **FE** is a static bundle with no state of its own: it fetches `/map` once per repo (an indexed repo is immutable) and shows one scope at a time, computed client-side: the repo's top-level areas, or one area with its children; clicking an area drills in (the card slides into the parent slot, the children animate in, the camera eases), a breadcrumb goes back; progress is polled (`GET /repos`, `GET /nodes/{id}/deep-dive` every 3 s, give up after 15 min, because a dead-lettered job never produces a row). The deep dive page is shown in a sandboxed `<iframe>` pointing at the API's HTML route, so its CSP applies unchanged.

## 4. Data model (Postgres)

Defined in `app/models/` (one file per entity); each follows `XBase` → `X` (table) → `XRead` (API).

- **users**: id, github_id (unique), login, access_token_enc, created_at. Created by the OAuth callback (upsert on github_id).
- **repos**: id, url (unique), commit_sha, status (`indexing | indexed | failed`), added_by → users (`SET NULL`; NULL = added anonymously), timestamps. Commit is a field, not its own entity.
- **nodes**: id, repo_id, name, description, paths, grouping (`llm | fallback`). A node is an **area** of the code.
  - `paths`: repo-relative files or folder prefixes that make up the area; a deep dive writes about exactly these. Each must exist in the repo at the pinned commit. Areas may overlap; there is no exactly-once rule. At least one path per node (`CHECK cardinality(paths) > 0`).
  - No `parent_id`, no children list, no depth: all connections between nodes are edge rows.
- **edges**: id, source_id → nodes, target_id → nodes, kind (`contains` now; `relates` later), label. Directed; one edge per (source, target); no self-loops.
  - `contains` is the tree. A partial unique index on `target_id WHERE kind = 'contains'` lets the database guarantee at most one parent, so the tree can't silently become a graph.
  - Top-level areas are nodes with no incoming `contains` edge; there is no root node (the repo row is the root).
  - **Why edges and not `parent_id`.** Gained: one relationship table, and `/map` is naturally `{nodes, edges}`, the shape canvas libraries (e.g. React Flow) take. Lost: "children of X" and "top level" become a join and an anti-join instead of a column lookup.
  - **Cycles: neither design prevents them.** `parent_id` allows `A.parent = B, B.parent = A` just as edges allow `A contains B contains A`. Both give "at most one parent" (a column vs. the partial unique index); neither gives acyclicity. So on cycles, edges aren't worse.
  - **Why cycles can't happen in v1:** only the indexer writes `contains` edges, it builds them top-down from its own recursion (a child is always created after its parent), all in one transaction, and the tree is immutable afterwards. Users never write edges.
  - **When re-indexing arrives (after v1): versioned snapshots.** A re-index builds a new, immutable tree for the new commit in one transaction, and the repo points to its current version. The argument above still holds per version, and deep dives keep pointing at the version and commit they were made from, which gives staleness detection almost for free. Rejected: updating the tree in place, which needs a cycle guard on every edge insert (a recursive-CTE "is the target an ancestor of the source?" check, or a trigger doing the same). That's more code, and updates are where bugs creep in.
- **deep_dives**: id, node_id (unique: one per node), object_key, created_at. The page itself is in the bucket under `sha256(html).html`; the row only points at it. No status column: no row means not written yet.
- **interview_questions**: id, deep_dive_id (→ deep_dives, cascade, indexed), question, answer. The self-quiz bank, written in the same transaction as its deep dive row.
- `/repos` only shows **indexed** repos.

## 5. API (REST + SSE)

```
GET  /repos                      indexed repos
POST /repos                      add + start indexing → 202 {url}  (normalized; no id, the worker creates the row)
                                 400 {detail: git's fatal line} if `git ls-remote` can't read the repo (private, missing, down)
GET  /repos/{id}/map             the whole tree: {nodes, edges}
GET  /auth/github/login          → GitHub (sets the state cookie)
GET  /auth/github/callback       code+state → upsert user, set session cookie, → /
GET  /auth/me                    UserRead | null
GET  /auth/github/repos          the user's GitHub repos (full_name, html_url, private); 401 when logged out
GET  /nodes/{id}                 node + its children
POST /nodes/{id}/deep-dive       generate the node's deep dive → 202 {node_id} (idempotent, queued once)
GET  /nodes/{id}/deep-dive       its metadata; 404 until written
GET  /nodes/{id}/deep-dive/html  the page, proxied from the private bucket, with a CSP header
```
- Not GraphQL: one client that I own, immutable cacheable snapshots; GraphQL's benefit is many clients with different needs.
- Address any single item by its own ID; nest only one level. A deep dive is addressed through its node because there is exactly one per node.
- SSE for progress later (deferred with jobs). Until then the frontend polls (§3).
- `GET /` and anything that isn't an API route serve the frontend bundle when `frontend/dist` exists (`StaticFiles(html=True)`, mounted last).

## 6. Queue: Redis Streams

- **Gateway writes only to Redis.** One Lua script atomically does `SET NX` on a dedup marker + `XADD` of the job. If it fails, the gateway returns 503 and the client retries. No dual write.
  - Dedup key: `dedup:repo:{normalized url}`. Stream: `jobs:index`. The job is one `payload` field holding `RepoCreate` as JSON; the worker validates it with the same class.
  - The Lua script is a generic wrapper (`app/queue/`) with no repo knowledge; `app/indexing/` binds it to these names.
  - Every job also carries its own marker in a `dedup_key` field, so the queue layer can free it on dead-letter without parsing the payload (which may be the thing that's broken).
- **Worker** (consumer group `indexers`) skips a job whose repo already has a SHA, otherwise clones and inserts the row (`ON CONFLICT (url) DO NOTHING`), then `XACK`s only after the commit. A failed job is not acked; it stays pending.
- **One loop for both workers** (`app/queue/work_loop.py`): reclaim an abandoned job, else read a new one → dead-letter it if over the limit → run it under a lease → `XACK`. The reaper lives inside every worker's loop, not in a separate process: no extra service, and it runs as long as any worker does.
- **Leases** (60 s, `JOB_LEASE_S`): `XREADGROUP` puts the job in the pending list. A heartbeat thread renews it every 20 s with one Lua script: `XPENDING` checks this consumer still owns the entry, then `XCLAIM … 0 JUSTID` resets its idle time without bumping the delivery count. The ownership check stops a stalled worker from stealing back a job the reaper already handed to someone else; such a worker logs it and finishes anyway. The lease is renewed for as long as the job runs, so it's sized to detect a dead worker, not to fit a job (an index job runs for minutes).
- **Reaper:** `XAUTOCLAIM … COUNT 1` takes the oldest job idle past the lease; `XPENDING` gives its delivery count. A failed job just isn't acked, so it comes back after one lease of idle time: that wait is the retry backoff.
- **Dead letter** (`dead:index`, `dead:deep_dive`): on the 4th delivery (`JOB_MAX_DELIVERIES = 3`), one `MULTI` does `XADD` to the DLQ (with `original_id`), `XACK`, and `DEL` of the dedup marker, so the repo or node can be queued again. No `failed` row is written: the next attempt's `ON CONFLICT` insert would hit it and silently drop its tree. Unreadable repos never get this far: `POST /repos` runs `git ls-remote` first and answers 400 with git's reason, so the DLQ only sees failures that happened after access was proven.
- **Idempotent workers, no fencing token:** delivery is at-least-once and zombie workers are possible, but every final write is insert-once (`ON CONFLICT (url)` / `(node_id) DO NOTHING`). The first commit wins and a zombie's late write does nothing, so the unique key is the fence. A fencing token earns its keep only for writes that overwrite.
- **Graceful shutdown:** SIGTERM/SIGINT set a stop flag; the worker finishes the current job, acks, and exits (an idle worker within one read block, 5 s).
- **Fairness (after v1, with multi-user):** per-user queues + round robin over an `active_users` ring, plus a per-user concurrency cap.
- **Redis config:** AOF `everysec`; `noeviction` (or TTLs only on cache keys with `volatile-lru`) so queue state is never evicted. The client's socket timeout (15 s, `REDIS_SOCKET_TIMEOUT_S`) is set explicitly and must outlast the 5 s blocking read; redis-py 8's 5 s default made every idle read crash the worker.
- Why not Postgres queue: with the gateway writing only to Redis, the dual-write argument doesn't apply, and Streams gives consumer groups, leases and recovery hands-on.

## 7. Indexing

- Shallow clone, latest commit only. Only code: filter lockfiles, generated, vendored, binaries, assets, and files that commonly hold secrets (`.env*`, keys, `.npmrc`, ...): agents can read any file in their list and would send its contents to the LLM provider.
- `python -m app.indexing.index_local <folder> <url>` indexes a local folder without the queue (copied into a one-commit repo first), e.g. to map this repo itself.
- **Agentic, hierarchical grouping.** The checkout is on disk; agents explore it with read-only tools instead of receiving files in the prompt.
  - The top agent's scope is the whole repo; it returns the top-level areas through a `submit_areas` tool.
  - **Our code, not the agent, starts subagents:** one per returned area, scope = that area's paths, run in parallel. Each returns its sub-areas or "leaf" (an empty list). Validation, recursion, parallelism and cost stay deterministic and testable.
  - Level by level: all areas of one level are split in parallel (a bounded thread pool), then the next level. No agent waits on another inside the pool, so the pool can't deadlock.
  - A scope with a single file is never given an agent: one file can't be split.
  - Termination without depth limits: an area may not hold every file its parent holds (validation rule), so each level strictly shrinks.
- **Tools** (read-only, confined to the checkout *and* the agent's scope; `../` and symlink escapes rejected):
  - big picture: `tree` (folders, file counts, languages), `outline` (classes/functions + signatures + docstring first lines, via griffe), `imports` (dependencies and dependents, via grimp), `clusters` (import-graph communities and central modules, via grimp + networkx), `manifests` (pyproject, package.json, Dockerfile, compose, README; trimmed)
  - detail: `grep` (`git grep`), `read_file` (line range)
  - answer: `submit_areas`
  - Python-only analysis for now (griffe, grimp); other languages fall back to tree/grep/read_file. grimp resolves packages through `find_spec`, so it runs in a subprocess whose only path is the checkout (otherwise a repo package named `app` would resolve to ours).
- **Contract (Pydantic), per agent answer:** each area has a non-empty name (unique among siblings), a description and at least one path; every path exists in the repo *and* lies inside the agent's scope. No depth or child-count limits.
- **Failure handling:** an invalid answer is retried once with the validation error fed back. If it's still invalid, *that node only* falls back to directory grouping: its children are its immediate subfolders, marked `grouping = fallback`, and they are explored by agents like any other area. The rest of the tree is kept. A bad answer (`AgentFailed`, `GatewayAnswerError`) falls back; an unreachable gateway (HTTP error) fails the job so the queue retries it, instead of producing a tree that is fallback everywhere. With 20-40 agents per repo, failing the job instead would lose whole trees often (2% per agent -> ~45% of 30-agent jobs).
- **Safety budget:** a per-agent turn ceiling (`max_turns = 15`) that only stops runaway loops, set from the first real run (54 agents, max 5 turns, most 2-3) with 3x headroom. When it's reached, the agent is told to wrap up and gets 3 more turns (`wrap_up_turns`) to submit; only then is it stopped. Every agent logs turns, tool calls, rejected answers, tokens and duration, so the numbers keep following real runs.
- **Leaves:** the prompt tells agents not to split an area a developer would read in one sitting (a handful of small files with one purpose). The first run split down to 1-3-file areas, which cost agents without making the map more useful; with the line, a rerun went from 54 to 42 areas and from 15 to 5 tiny leaves, using 14% fewer tokens. This is guidance in the prompt, not a shape limit the validator enforces.
- **Tests stay with their area:** the prompt puts each test file in the area it tests, not in a separate "Tests" area, because a deep dive on an area should see its tests (its paths feed the sparse checkout). Also prompt guidance, not a validator rule.
- **Agent cap: at most 3 agents at once across every worker** (`semaphore_slot`, Redis key `slots:agents`), so many agents can't overload the machine. A slot covers one whole agent run, tools included. It's a lease (60 s) renewed by a heartbeat thread every 20 s; a crashed worker's slot frees itself when the lease runs out. Acquire is one Lua script (drop expired holders → count → add) using Redis's clock. Not fair (no FIFO): fairness comes after v1, with multi-user.
- All agents finish in memory; nodes and their `contains` edges are written in the same transaction as the repo row.
- Reference reading: GitDiagram (bounded tree + sampled source excerpts, strict validation, deterministic compile) and CodeBoarding (static analysis via language servers + LLM naming, depth cap + expand on demand).
- Not yet: tree-sitter for non-Python analysis, expand-on-demand, caching per-node results so a retried job doesn't re-pay for finished agents.

## 8. Deep dives

- **Flow** (`app/deep_dive/`): job `{node_id}` → skip if a row exists → checkout of the repo at the pinned commit (secret and vendored files filtered out by `code_files`) → agent → render HTML → upload → insert row (`ON CONFLICT (node_id) DO NOTHING`) → `XACK`.
  - Stream `jobs:deep_dive`, group `deep_divers`, dedup key `dedup:deep_dive:{node_id}`, same Lua enqueue as indexing.
  - Upload before insert: a crash in between leaves an orphan object that the retry overwrites (same key), never a row pointing at nothing.
  - The read transaction ends before the agent runs, so no connection sits idle in a transaction for minutes.
- **Sparse clone** (`app/git/sparse_clone.py`): `init` → `remote add origin -- <url>` → non-cone `sparse-checkout set /<path>…` → `fetch --depth 1 --filter=blob:none origin <sha>` → `checkout --detach`. Fetches by SHA because the branch may have moved; only the checked-out blobs are downloaded. The SHA must be 40 hex chars.
- **Agent:** `run_agent` with the same read-only workspace tools as indexing. It writes about the node's paths but can read the whole repo: in the first content review, most wrong claims were edge cases settled by code outside the node (callers, fallbacks), which a node-scoped agent couldn't see. It holds one of the agent slots shared with indexing (same Redis key and limit), so the two services together never exceed the gateway's capacity. The writer and the verifier run as a two-node LangGraph (`app/deep_dive/graph/`) with a Postgres checkpointer, thread id = node id. A delivery that dies after an agent (crash, bucket or DB failure) resumes at the failed node; one whose row never landed reuses the finished answer; the thread is deleted after the commit. Answers sit in state as JSON because a `Diagram` can only be rebuilt with the live `AnswerContext`; readers re-validate, which re-renders diagrams and re-checks excerpts against the fresh clone. Render, upload and insert stay outside the graph: cheap, and they need per-job resources. The checkpointer's tables are the one schema Alembic doesn't own; LangGraph creates and migrates them itself (`setup()` at worker start).
- **Verifier (off by default, `DEEP_DIVE_VERIFY=true` to enable):** in review it raised the score from 83 to 84 and accuracy from 8 to 9 for about $0.40 more per deep dive, so v1 ships the writer alone. When on: a second, fresh agent (`verify_deep_dive.py`, model `DEEP_DIVE_VERIFIER_MODEL`, defaults to `LLM_MODEL`) gets the writer's answer as JSON, checks each claim against the code (absolute words, which exception or value a caller gets, defaults, counterfactuals, fixes, quiz answers), and returns `VerifiedAnswer`: the corrections it made, plus the answer with only those claims changed. The same validator checks it. Why a separate agent: across four review rounds the writer kept errors that its own prompt had rules for, since it can't audit a long answer in the context that produced it. If the verifier fails, the already-valid draft ships unverified (logged), so verification never costs a page. No code execution yet: running an untrusted repo's code waits for the sandbox.
- **Input:** repo, node name, description, breadcrumb of ancestors (walked up `contains` edges), scope.
- **Output contract** (`app/deep_dive/answer/`): `DeepDiveAnswer` = title, sections of blocks (paragraph | callout tip/info/warning | code excerpt | diagram | svg figure), 3 to 6 `interview_questions` (question + spoken-style answer, stored as rows for self-quizzing and rendered as a hide-the-answer quiz), and an optional `tech_stack` (per technology: role, pros, cons, alternatives with trade-offs, fit with the overall design). `InterviewQuestionDraft` extends the table's `InterviewQuestionBase` and adds only the humanizer check, so the shape is declared once. Validators get an `AnswerContext` (the checkout + the diagram renderer).
  - Code excerpts are a path + line range, checked against the checkout (in the checkout, inside the file, ≤ 25 lines). The renderer copies the real lines, so the model can't invent code.
  - Diagrams are `language` (mermaid | graphviz) + source + caption. The source is rendered through Kroki during validation and the SVG kept on the block (a private attribute, so the model never writes SVG for a diagram). A syntax error is a normal rejection the agent fixes; a Kroki outage propagates and fails the job, so the queue retries it instead of burning the agent's retries.
  - SVG figures are drawn by the model for what a layout engine can't draw (byte layouts, buffers, timelines). Checked at the boundary: well-formed XML, root `<svg>` in the SVG namespace, a `viewBox`, no `<script>`, ≤ 40 KB. Rendered the same way as diagrams, through `<img>`.
- **Style:** Hello Interview structure (opening, worked example, core concepts, internals, one section per job, what breaks, design choices, interview questions, summary) and the humanizer rules (blader/humanizer v4).
  - Mechanical tells (dashes, banned words and phrases, in `humanizer_rules.py`) are enforced by a validator on every text field; a hit rejects the answer with every hit listed, so one retry can fix all. Also enforced: no exact generic headings (`generic_headings.py`), a summary heading only on the last section, 3-6 interview questions. Context-dependent rules stay in the prompt, because a false rejection costs a retry and two fail the run. The prompt reads the banned lists from the same file.
- **Page design:** no JavaScript (the CSP forbids it), so everything is CSS or native HTML: a contents list (sticky sidebar, folded on phones), reading time and the questions up front (pretesting), the quiz with answers in closed `<details>` (testing effect), the summary last as key takeaways (serial position), captions above code, callouts labelled by text and icon as well as color.
- **HTML:** the model never writes markup. Jinja2 with autoescape renders the typed answer; backticks become `<code>` after escaping. The page carries a CSP (`default-src 'none'`), and the API sends the same header: defense in depth against prompt-injected repo content.
- **Visuals:** every section except the summary (the last one, when there are several) carries at least one diagram (Mermaid or Graphviz) or model-drawn SVG. A `DeepDiveAnswer` validator enforces it and names every section that lacks one, so one retry fixes them all; the summary is exempt because it adds no new claims to draw.
  - Diagrams render to SVG on our side through a self-hosted Kroki (`app/kroki/`, compose services `kroki` + `kroki-mermaid`), because the page runs no scripts. Rejected: mermaid-cli (Node + Chrome in every worker), mermaid.ink (repo content leaves the machine), Graphviz alone (no sequence diagrams). Kroki's default safe mode stops DOT from reading local files.
  - Mermaid for sequences, state and ER; Graphviz for dependency and structure graphs with many nodes.
  - Every SVG is embedded as `<img src="data:image/svg+xml;base64,…">`: a browser runs no scripts and loads nothing external for an SVG image, so a hostile SVG is inert and the CSP stays unchanged.
- **Storage:** content-addressed key `sha256(html).html` in a private bucket. Retries write the same key; a key never changes meaning. The wrapper (`app/storage/`) knows nothing about deep dives.
- Reaper, DLQ and graceful shutdown: the shared loop in §6.
- Not yet: presigned URLs instead of proxying, Git history/blame for deep dives.

## 9. Redis roles (summary)

- Queue (Streams + consumer groups), dedup markers, leases, DLQ.
- Cache for expensive results keyed on immutable SHAs (index cache deferred until the output shape is known; deep dives are cached by their Postgres row + bucket object).
- Rate limits and progress pub/sub (later).

## 10. Scaling notes (for interviews; not needed for v1)

SSE connections: each is a socket = a file descriptor; the per-process limit (`ulimit -n`, `RLIMIT_NOFILE`, often 1024) is a config value.
- Option 1: raise the limit (`LimitNOFILE`, `--ulimit`) and run normal instances. Cheap; deploys drop connections.
- Option 2: separate connection tier / push gateway subscribed to Redis. Survives deploys, scales independently, isolates connection storms; extra service.
- With >1 instance: workers publish progress to Redis pub/sub, each instance forwards to its clients.
- v1: neither needed; one default instance.