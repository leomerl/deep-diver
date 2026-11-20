import httpx
from pydantic import BaseModel

TOKEN_URL = "https://github.com/login/oauth/access_token"


class GitHubAuthError(Exception):
    """GitHub refused the code (expired, reused, or wrong client secret)."""


class _TokenResponse(BaseModel):
    # GitHub answers 200 for failures too, with `error` instead of a token.
    access_token: str | None = None
    error: str | None = None


def exchange_code(client_id: str, client_secret: str, code: str, timeout_s: float) -> str:
    """Trade the callback's one-time code for the user's access token."""
    response = httpx.post(
        TOKEN_URL,
        data={"client_id": client_id, "client_secret": client_secret, "code": code},
        headers={"Accept": "application/json"},
        timeout=timeout_s,
    )
    response.raise_for_status()
    body = _TokenResponse.model_validate_json(response.content)
    if body.access_token is None:
        raise GitHubAuthError(body.error or "no access_token in response")
    return body.access_token
