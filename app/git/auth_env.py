from base64 import b64encode
from urllib.parse import urlsplit

# GitHub accepts any username with a token as the password; GitLab and Bitbucket use the same Basic scheme.
TOKEN_USER = "x-access-token"


def auth_env(url: str, token: str | None) -> dict[str, str]:
    """Environment that makes git send `token` to `url`'s host. Empty when there is no token.

    Config goes through GIT_CONFIG_* variables, not `-c`, so the token never shows in a process listing.
    Scoped to the host (http.<origin>.extraheader): a redirect elsewhere would not receive it.
    """
    if token is None:
        return {}
    origin = urlsplit(url)
    credentials = b64encode(f"{TOKEN_USER}:{token}".encode()).decode()
    return {
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": f"http.{origin.scheme}://{origin.netloc}/.extraheader",
        "GIT_CONFIG_VALUE_0": f"Authorization: Basic {credentials}",
    }
