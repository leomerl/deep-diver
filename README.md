# deep-diver

Maps a git repo into a tree of code areas, and writes an AI deep dive about any area you click.

You add a repo by URL (or pick one from your GitHub account). A worker clones it and an agent groups the code into areas and sub-areas. The frontend draws that tree as a map. Clicking an area queues a deep dive: one agent writes the page from the code, a second one verifies it against the code, and the result is stored as an HTML page you can read in the app. A page can also get a notebook: short Python cells about the same code that run in your browser (Pyodide).

[DESIGN.md](DESIGN.md) holds the requirements, the architecture and the reason behind each decision.

## Run it

You need Docker with Compose, and an Anthropic API key.

1. Create `.env` in the repo root:

   ```
   SECRET_KEY=<any long random string>
   ANTHROPIC_API_KEY=<your key>
   # Optional: GitHub login, needed only for private repos
   GITHUB_CLIENT_ID=
   GITHUB_CLIENT_SECRET=
   ```

   `SECRET_KEY` signs the session cookie and encrypts stored GitHub tokens, so changing it logs everyone out and makes stored tokens unreadable.

2. Start everything:

   ```
   docker compose up -d --build
   ```

   Migrations are applied on start. The app is at http://localhost:8000.

For GitHub login, create a GitHub OAuth App with the callback URL `http://localhost:8000/auth/github/callback` and put its client id and secret in `.env`.

## How it is built

| Part | What it does |
|------|--------------|
| `app/api` | FastAPI: the REST API, and the built frontend at `/` |
| `app/indexing` | Worker that clones a repo and builds its tree of areas |
| `app/deep_dive` | Worker that writes and verifies a deep dive (LangGraph) |
| `app/deep_dive/notebook_worker.py` | Worker that writes a runnable notebook for a finished deep dive |
| `app/jobs` | The Jobs page's view of each queue: state, tries, and the write › verify › notebook chain |
| `app/mcp_server` | MCP server at `/mcp`, so an agent can read the maps and deep dives |
| `app/gateway` | LLM gateway: the only service that holds the Anthropic key |
| `app/queue` | Job queue on Redis Streams, at-least-once delivery |
| `app/models` | SQLModel classes: the tables and the API schemas |
| `frontend/` | React + TypeScript + Vite; React Flow draws the map |

Postgres is the source of truth, Redis is the queue, and MinIO (S3 API) stores the deep dive pages. The workers run untrusted repo content, so they run in locked-down containers on an internal network. Their only way out is a proxy that allows HTTPS to the git hosts.

## Development

Backend, with [uv](https://docs.astral.sh/uv/):

```
uv sync
uv run pytest
```

Frontend:

```
cd frontend
npm install --legacy-peer-deps
npm run dev      # Vite dev server, proxies API calls to localhost:8000
npm test
npm run types    # regenerate API types from the OpenAPI spec
```

The database schema comes from the SQLModel classes. After changing a model, generate a migration and review it:

```
uv run alembic revision --autogenerate -m "what changed"
```
