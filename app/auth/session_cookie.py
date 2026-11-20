from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.config import SECRET_KEY, SESSION_MAX_AGE_S

SESSION_COOKIE = "session"
_SALT = "session"  # keeps a session value from doubling as any other signed value


def sign_user_id(user_id: int) -> str:
    return URLSafeTimedSerializer(SECRET_KEY, salt=_SALT).dumps(user_id)


def read_user_id(value: str | None) -> int | None:
    """The user id in a cookie value, or None when missing, tampered with, or older than SESSION_MAX_AGE_S."""
    if value is None:
        return None
    try:
        user_id: int = URLSafeTimedSerializer(SECRET_KEY, salt=_SALT).loads(value, max_age=SESSION_MAX_AGE_S)
    except BadSignature:
        return None
    return user_id
