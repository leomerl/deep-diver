from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api.frontend_files import FrontendFiles
from app.api.routes import (
    auth, deep_dive_list, deep_dives, interview_questions, jobs, nodes, repo_deep_dives, repos, settings,
)
from app.mcp_server import server as mcp_server

# `npm run build` output. Mounted last, so it never shadows the API routes above it.
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

# Stateless JSON: the tools are read-only lookups, so there is no session to keep and an API restart doesn't
# break connected agents. The SDK's default Host check stays on: it accepts only localhost, which is what keeps a
# web page from reaching this unauthenticated endpoint through DNS rebinding.
# TODO [MCP:MEDIUM] localhost only; a deployed API needs auth here and its own host in `transport_security`.
mcp_http = mcp_server.streamable_http_app(stateless_http=True, json_response=True)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # The MCP transport handles requests in this task group; without it every /mcp call fails.
    async with mcp_server.session_manager.run():
        yield


app = FastAPI(title="deep-diver", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(repos.router)
app.include_router(nodes.router)
app.include_router(deep_dives.router)
app.include_router(repo_deep_dives.router)
app.include_router(deep_dive_list.router)
app.include_router(interview_questions.router)
app.include_router(settings.router)
app.include_router(jobs.router)
# POST /mcp. The route itself, not a mount: a mount at /mcp only matches /mcp/, and clients post to /mcp.
app.router.routes.extend(mcp_http.routes)
# Only when built: tests and API-only deploys have no bundle, and StaticFiles raises on a missing directory.
if FRONTEND_DIST.is_dir():
    app.mount("/", FrontendFiles(directory=FRONTEND_DIST, html=True), name="frontend")
