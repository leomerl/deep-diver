from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.frontend_files import NOTEBOOK_WORKER, FrontendFiles


def test_only_the_notebook_worker_gets_the_lockdown_csp_naming_this_origin(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / NOTEBOOK_WORKER).write_text("self.onmessage = () => {};")
    (tmp_path / "assets" / "index.js").write_text("console.log(1);")
    app = FastAPI()
    app.mount("/", FrontendFiles(directory=tmp_path), name="frontend")
    client = TestClient(app, base_url="https://dd.example")

    csp = client.get(f"/assets/{NOTEBOOK_WORKER}").headers["content-security-policy"]
    assert "connect-src https://dd.example/pyodide/" in csp
    assert "default-src 'none'" in csp
    assert "content-security-policy" not in client.get("/assets/index.js").headers
