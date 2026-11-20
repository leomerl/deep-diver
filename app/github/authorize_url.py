from urllib.parse import urlencode

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
# `repo` is the only OAuth App scope that reads private repositories (it also grants write; we never use it).
SCOPE = "repo"


def authorize_url(client_id: str, state: str) -> str:
    """Where to send the browser. No redirect_uri: GitHub uses the one registered on the OAuth App."""
    return f"{AUTHORIZE_URL}?{urlencode({'client_id': client_id, 'state': state, 'scope': SCOPE})}"
