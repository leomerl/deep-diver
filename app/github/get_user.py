import httpx

from .github_user import GitHubUser
from .headers import api_headers

USER_URL = "https://api.github.com/user"


def get_user(token: str, timeout_s: float) -> GitHubUser:
    response = httpx.get(USER_URL, headers=api_headers(token), timeout=timeout_s)
    response.raise_for_status()
    return GitHubUser.model_validate_json(response.content)
