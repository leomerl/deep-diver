import secrets

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import col

from app.auth import SESSION_COOKIE, RequiredUser, CurrentUser, decrypt_token, encrypt_token, sign_user_id
from app.config import GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, GITHUB_TIMEOUT_S, SESSION_MAX_AGE_S
from app.db import SessionDep
from app.github import GitHubAuthError, GitHubRepo, authorize_url, exchange_code, get_user, list_repos
from app.models import User, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])

STATE_COOKIE = "oauth_state"
STATE_MAX_AGE_S = 600  # the time a user has to finish the GitHub page
AFTER_LOGIN = "/"


@router.get("/github/login")
def github_login(request: Request) -> RedirectResponse:
    """Send the browser to GitHub. The random `state` comes back in the callback and must match this cookie (CSRF)."""
    if not GITHUB_CLIENT_ID:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "GitHub login is not configured")
    state = secrets.token_urlsafe(32)
    response = RedirectResponse(authorize_url(GITHUB_CLIENT_ID, state))
    response.set_cookie(STATE_COOKIE, state, max_age=STATE_MAX_AGE_S, httponly=True, samesite="lax", secure=_https(request))
    return response


@router.get("/github/callback")
def github_callback(request: Request, session: SessionDep, code: str, state: str) -> RedirectResponse:
    if not secrets.compare_digest(state, request.cookies.get(STATE_COOKIE, "")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "login state mismatch; start again")
    try:
        token = exchange_code(GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, code, GITHUB_TIMEOUT_S)
        github_user = get_user(token, GITHUB_TIMEOUT_S)
    except (GitHubAuthError, httpx.HTTPError) as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"GitHub login failed: {e}") from e
    # Upsert on github_id: a returning user gets their login and token refreshed, never a second row.
    user = User(github_id=github_user.id, login=github_user.login, access_token_enc=encrypt_token(token))
    values = user.model_dump(exclude={"id"})
    user_id = session.exec(
        insert(User)
        .values(**values)
        .on_conflict_do_update(
            index_elements=[col(User.github_id)], set_={"login": values["login"], "access_token_enc": values["access_token_enc"]}
        )
        .returning(col(User.id))
    ).scalar_one()
    session.commit()
    response = RedirectResponse(AFTER_LOGIN)
    response.delete_cookie(STATE_COOKIE)
    response.set_cookie(
        SESSION_COOKIE, sign_user_id(user_id), max_age=SESSION_MAX_AGE_S, httponly=True, samesite="lax", secure=_https(request)
    )
    return response


@router.get("/me")
def me(user: CurrentUser) -> UserRead | None:
    """The logged-in user, or null."""
    return None if user is None else UserRead.model_validate(user)


@router.get("/github/repos")
def github_repos(user: RequiredUser) -> list[GitHubRepo]:
    """Every repo the user's token can read, private ones included."""
    try:
        return list_repos(decrypt_token(user.access_token_enc), GITHUB_TIMEOUT_S)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == status.HTTP_401_UNAUTHORIZED:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "GitHub rejected the token; log in again") from e
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "GitHub did not answer") from e
    except httpx.HTTPError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "GitHub did not answer") from e


def _https(request: Request) -> bool:
    # Cookies are marked Secure only over https, so local http dev keeps working.
    return request.url.scheme == "https"
