import re
from urllib.parse import urlsplit

from app.repo_url.allowed_hosts import ALLOWED_HOSTS

HTTPS = "https"
GIT_SUFFIX = ".git"
MIN_PATH_SEGMENTS = 2  # owner/repo; GitLab subgroups add more
SEGMENT = re.compile(r"^(?!\.+$)[A-Za-z0-9._-]+$")  # no "..", no "%", no spaces


def normalize_repo_url(raw: str) -> str:
    """Canonical repo URL, so one repo has exactly one key. Raises ValueError.

    The result is handed to `git clone`, so anything unusual is rejected rather than repaired.
    """
    parts = urlsplit(raw.strip())
    host = (parts.hostname or "").lower()
    segments = [s for s in parts.path.split("/") if s]
    if segments:
        segments[-1] = segments[-1].removesuffix(GIT_SUFFIX)

    if parts.scheme != HTTPS:
        raise ValueError("repo URL must use https")
    if parts.username or parts.password:
        raise ValueError("repo URL must not contain credentials")
    if parts.port is not None or parts.query or parts.fragment:
        raise ValueError("repo URL must not have a port, query or fragment")
    if host not in ALLOWED_HOSTS:
        raise ValueError(f"host must be one of: {', '.join(sorted(ALLOWED_HOSTS))}")
    if len(segments) < MIN_PATH_SEGMENTS or not all(SEGMENT.match(s) for s in segments):
        raise ValueError("repo URL must look like https://host/owner/repo")
    # TODO [INDEXING:LOW] GitHub paths are case-insensitive, so Owner/Repo and owner/repo dedup separately
    return f"{HTTPS}://{host}/{'/'.join(segments)}"
