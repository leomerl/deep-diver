from app.indexing.code_files import code_files


def test_drops_vendored_generated_lock_and_asset_files() -> None:
    kept = ["app/main.py", "web/src/App.tsx", "Makefile", "lib/builder.py"]
    dropped = [
        "web/node_modules/react/index.js", "Vendor/x.go", "poetry.lock", "web/dist/app.min.js",
        "docs/logo.PNG", "api/v1_pb2.py",
    ]
    assert code_files(kept + dropped) == kept


def test_drops_files_that_commonly_hold_secrets() -> None:
    # An agent could read these and send their contents to the LLM provider.
    kept = ["app/config.py", "docs/environment.md"]
    dropped = [".env", "deploy/.env.production", "certs/server.PEM", "keys/deploy.key", "home/.npmrc", "id_rsa"]
    assert code_files(kept + dropped) == kept
