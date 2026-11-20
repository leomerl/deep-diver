from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status

from app.db import SessionDep
from app.models import User

from .session_cookie import SESSION_COOKIE, read_user_id


def get_current_user(session: SessionDep, cookie: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None) -> User | None:
    user_id = read_user_id(cookie)
    return None if user_id is None else session.get(User, user_id)


CurrentUser = Annotated[User | None, Depends(get_current_user)]


def require_user(user: CurrentUser) -> User:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "log in with GitHub first")
    return user


RequiredUser = Annotated[User, Depends(require_user)]
