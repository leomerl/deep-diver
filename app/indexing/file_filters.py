# Files that aren't hand-written code: they would add noise to the map and cost tokens in deep dives.
# Matched case-insensitively.

SKIPPED_DIRS: frozenset[str] = frozenset({
    "node_modules", "vendor", "third_party", "dist", "build", "target", "out",
    "__pycache__", ".venv", "venv", ".tox", ".mypy_cache", ".pytest_cache", ".next", ".idea", ".vscode",
})

LOCKFILES: frozenset[str] = frozenset({
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "poetry.lock", "uv.lock",
    "pipfile.lock", "cargo.lock", "gemfile.lock", "composer.lock", "go.sum",
})

SKIPPED_SUFFIXES: tuple[str, ...] = (
    # minified / generated
    ".min.js", ".min.css", ".map", ".pyc", ".pb.go", "_pb2.py",
    # images, media, fonts
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg", ".bmp",
    ".mp3", ".mp4", ".mov", ".wav", ".woff", ".woff2", ".ttf", ".otf", ".eot",
    # archives, binaries, documents
    ".zip", ".gz", ".tar", ".tgz", ".7z", ".rar", ".jar", ".war", ".whl",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".pdf",
)

# Files that commonly hold secrets. An agent could read them and send their contents to the LLM provider,
# so they never enter the file list. Matched case-insensitively, like the rest.
SECRET_NAMES: frozenset[str] = frozenset({
    ".env", ".npmrc", ".pypirc", ".netrc", ".htpasswd", "credentials.json", "id_rsa", "id_ed25519", "id_ecdsa",
})
SECRET_PREFIXES: tuple[str, ...] = (".env.",)  # .env.local, .env.production, ...
SECRET_SUFFIXES: tuple[str, ...] = (".pem", ".key", ".p12", ".pfx", ".keystore", ".jks")
