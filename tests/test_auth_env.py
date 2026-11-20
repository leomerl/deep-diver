from base64 import b64decode

from app.git import auth_env


def test_no_token_means_no_env() -> None:
    assert auth_env("https://github.com/o/r", None) == {}


def test_token_becomes_a_basic_header_scoped_to_the_host() -> None:
    env = auth_env("https://github.com/o/r", "tok")
    assert env["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraheader"
    scheme, credentials = env["GIT_CONFIG_VALUE_0"].removeprefix("Authorization: ").split(" ")
    assert (scheme, b64decode(credentials)) == ("Basic", b"x-access-token:tok")
