import os
from pathlib import Path

from starlette.requests import Request
from starlette.responses import Response
from starlette.staticfiles import PathLike, StaticFiles
from starlette.types import Scope

from app.deep_dive.content_security_policy import NOTEBOOK_WORKER_CSP

# Fixed by `worker.rollupOptions` in frontend/vite.config.ts, so the name carries no content hash.
NOTEBOOK_WORKER = "notebook-worker.js"


class FrontendFiles(StaticFiles):
    """The built frontend, with the notebook worker's lockdown header. A worker's CSP comes from its own response,
    not from the page that starts it."""

    def file_response(
        self, full_path: PathLike, stat_result: os.stat_result, scope: Scope, status_code: int = 200
    ) -> Response:
        response = super().file_response(full_path, stat_result, scope, status_code)
        if Path(full_path).name == NOTEBOOK_WORKER:
            origin = str(Request(scope).base_url).rstrip("/")
            response.headers["Content-Security-Policy"] = NOTEBOOK_WORKER_CSP.format(origin=origin)
        return response
