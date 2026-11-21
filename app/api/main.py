from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import (
    auth, deep_dive_list, deep_dives, interview_questions, nodes, repo_deep_dives, repos, settings,
)

# `npm run build` output. Mounted last, so it never shadows the API routes above it.
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

app = FastAPI(title="deep-diver")
app.include_router(auth.router)
app.include_router(repos.router)
app.include_router(nodes.router)
app.include_router(deep_dives.router)
app.include_router(repo_deep_dives.router)
app.include_router(deep_dive_list.router)
app.include_router(interview_questions.router)
app.include_router(settings.router)
# Only when built: tests and API-only deploys have no bundle, and StaticFiles raises on a missing directory.
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
