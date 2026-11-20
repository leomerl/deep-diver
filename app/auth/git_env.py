from sqlmodel import Session

from app.git import auth_env
from app.models import User

from .token_cipher import decrypt_token


def git_env(session: Session, url: str, user_id: int | None) -> dict[str, str]:
    """Git environment that clones `url` as `user_id`; empty for anonymous adds or a deleted user."""
    user = None if user_id is None else session.get(User, user_id)
    return {} if user is None else auth_env(url, decrypt_token(user.access_token_enc))
