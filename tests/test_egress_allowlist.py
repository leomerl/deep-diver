from pathlib import Path

from app.repo_url.allowed_hosts import ALLOWED_HOSTS

SQUID_CONF = Path(__file__).parent.parent / "egress" / "squid.conf"
ACL_PREFIX = ["acl", "git_hosts", "dstdomain"]


def test_proxy_allows_exactly_the_hosts_the_api_accepts() -> None:
    lines = (line.split() for line in SQUID_CONF.read_text().splitlines())
    hosts = next(words[len(ACL_PREFIX):] for words in lines if words[: len(ACL_PREFIX)] == ACL_PREFIX)
    assert frozenset(hosts) == ALLOWED_HOSTS
