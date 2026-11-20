import pytest

from app.repo_url import normalize_repo_url

CANONICAL = "https://github.com/fastapi/fastapi"


@pytest.mark.parametrize("raw", [
    CANONICAL,
    "https://GitHub.com/fastapi/fastapi",
    "https://github.com/fastapi/fastapi.git",
    "https://github.com/fastapi/fastapi/",
    "  https://github.com/fastapi/fastapi.git/  ",
])
def test_spellings_of_one_repo_share_one_url(raw: str) -> None:
    assert normalize_repo_url(raw) == CANONICAL


def test_gitlab_subgroups_and_dot_repos_are_valid() -> None:
    assert normalize_repo_url("https://gitlab.com/group/sub/repo") == "https://gitlab.com/group/sub/repo"
    assert normalize_repo_url("https://github.com/org/.github") == "https://github.com/org/.github"


@pytest.mark.parametrize("raw", [
    "http://github.com/a/b",                 # not https
    "file:///etc/passwd",                    # local file
    "--upload-pack=touch /tmp/x",            # git option injection
    "https://user:token@github.com/a/b",     # credentials
    "https://github.com:8443/a/b",           # port
    "https://github.com/a/b?x=1",            # query
    "https://internal.corp/a/b",             # not on the allowlist (SSRF)
    "https://169.254.169.254/latest/meta",   # cloud metadata endpoint
    "https://github.com/a",                  # no repo segment
    "https://github.com/a/..",               # path traversal
    "https://github.com/a/b%20c",            # encoded characters
    "https://github.com/a/.git",             # empty repo name
])
def test_rejected(raw: str) -> None:
    with pytest.raises(ValueError):
        normalize_repo_url(raw)
