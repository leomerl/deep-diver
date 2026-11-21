# deep-diver

Maps repos into a tree of code areas and generates AI deep dives on any node. [DESIGN.md](DESIGN.md) holds the requirements, architecture and decisions; read it before proposing anything.

Stack: Python 3.12, uv, SQLModel + Alembic, Postgres, Redis Streams, FastAPI and LangGraph later. Frontend in `frontend/`: React + TypeScript + Vite + React Flow; API types generated from OpenAPI (`npm run types`), never hand-written. Everything runs in compose: `docker compose up -d --build` (app at http://localhost:8000; `migrate` applies migrations on start).

## How we work

- This is an interview-prep project. Claude writes the code; the user has to be able to defend every line of it.
- Plan first, then build in small steps. Propose the next piece, wait for the user to pick, build only that piece, explain it, and stop. Never scaffold several files ahead.
- Explain each step at interview depth: what it does, why this choice, which alternatives were rejected and why, how it fails, and what an interviewer would ask about it.
- Add a dependency only in the step that first needs it.
- When a decision changes, update DESIGN.md so it describes the current state. No changelog or history in docs.
- Do not start long-running services and do not apply migrations (`alembic upgrade`) without asking. Generating a revision is fine.

## Code rules

**Schema-driven.** The typed models are the source of truth.
- DB tables are SQLModel classes. Migrations come from `alembic revision --autogenerate`, then get reviewed. Never hand-write DDL or `schema.sql`.
- Each entity follows `XBase` (shared fields) → `X(XBase, table=True)` (table) → `XRead(XBase)` (API response). Never re-declare a field that already exists on a model.
- Request and response schemas reuse these classes. Do not hand-copy a shape into a second model: two copies drift.
- Validate untrusted input (HTTP bodies, LLM output, queue payloads) with Pydantic at the boundary. Inside the boundary, trust the types.

**One responsibility per file.** One entity, service, router or worker per file. A package's `__init__.py` re-exports its public names, and does nothing else. Keep data lists (allowlists, filters, prompts) in their own files, apart from the code that uses them.

**Types.**
- Type hints on every function, including the return type.
- No `Any`, no `cast()`, no `# type: ignore` without a one-line reason. Reaching for one usually means a parse step is missing upstream.
- Use a `StrEnum` or a named constant for any string or number that carries meaning. No magic literals.
- Store enums as `sa.Enum(..., native_enum=False)` so adding a value needs no `ALTER TYPE`.

**Style.**
- Absolute imports (`from app.models import Repo`). A same-package `from .x import Y` is fine; `..` is not.
- Prefer expressions, comprehensions and early returns over reassigning variables and nested branches.
- Timestamps are timezone-aware UTC (`datetime.now(UTC)`, `DateTime(timezone=True)`).
- Constraints live in the database too: unique keys, foreign keys with `ondelete`, check constraints, and an index for every query the API makes. Name the query the index serves in a comment.

**Comments.** Few, in English, and only for the why the code can't state: a constraint, a failure mode, or a reason a simpler option was rejected. A comment that restates the code gets deleted. Module docstrings may explain a pattern once (see `app/models/__init__.py`). Tag deferred work as `TODO [AREA:LOW|MEDIUM|HIGH] ...`.

**Data safety.**
- A write and the history or side effects it needs go in one transaction. Inside a transaction, use the session you were given, never the global engine.
- Workers are idempotent: delivery is at-least-once (see DESIGN.md §6).
- Never swallow an error that would lose data. Let the operation fail.

**Layers (as integrations arrive).** Wrappers around third-party tools (git, LLM, Redis) take injected config and know nothing about repos or nodes. Domain code binds them to `app.config`. Wrapper code must not import domain modules.

**Tests** live in `tests/`, never beside the source.
