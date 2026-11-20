from app.indexing.file_filters import (
    LOCKFILES, SECRET_NAMES, SECRET_PREFIXES, SECRET_SUFFIXES, SKIPPED_DIRS, SKIPPED_SUFFIXES,
)


def code_files(paths: list[str]) -> list[str]:
    """Drop vendored, generated, lock, binary, asset and secret files."""
    return [path for path in paths if _is_code(path.lower())]


def _is_code(path: str) -> bool:
    *dirs, name = path.split("/")
    return (
        not SKIPPED_DIRS.intersection(dirs)
        and name not in LOCKFILES
        and not name.endswith(SKIPPED_SUFFIXES)
        and not _is_secret(name)
    )


def _is_secret(name: str) -> bool:
    return name in SECRET_NAMES or name.startswith(SECRET_PREFIXES) or name.endswith(SECRET_SUFFIXES)
