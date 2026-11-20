import httpx
from pydantic import TypeAdapter

from .github_repo import GitHubRepo
from .headers import api_headers

REPOS_URL = "https://api.github.com/user/repos"
PAGE_SIZE = 100  # GitHub's maximum
# Everything the token can read, not only owned repos.
AFFILIATION = "owner,collaborator,organization_member"
_REPOS = TypeAdapter(list[GitHubRepo])


def list_repos(token: str, timeout_s: float) -> list[GitHubRepo]:
    """The user's repos, most recently pushed first."""
    # shortcut: first page only (100 repos); follow the Link header when someone has more.
    response = httpx.get(
        REPOS_URL,
        params={"per_page": PAGE_SIZE, "sort": "pushed", "affiliation": AFFILIATION},
        headers=api_headers(token),
        timeout=timeout_s,
    )
    response.raise_for_status()
    return _REPOS.validate_json(response.content)
