# Files that say what a project is: its dependencies, entry points, services and purpose. Matched lowercase.
MANIFEST_NAMES: frozenset[str] = frozenset({
    "readme", "readme.md", "readme.rst", "readme.txt",
    "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
    "package.json", "go.mod", "cargo.toml", "pom.xml", "build.gradle", "build.gradle.kts",
    "dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml",
    "makefile", "procfile",
})
