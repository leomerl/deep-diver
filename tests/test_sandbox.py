"""Probes run inside the deep dive worker container. Opt-in: starts the egress proxy and one-shot worker containers."""
import os
import shutil
import subprocess
from textwrap import dedent

import pytest

OPT_IN_ENV = "SANDBOX_TESTS"
SERVICE = "deep-dive-worker"
PROXY_SERVICE = "egress"
PROBE_TIMEOUT_S = 120

pytestmark = pytest.mark.skipif(
    os.getenv(OPT_IN_ENV) != "1" or shutil.which("docker") is None,
    reason=f"set {OPT_IN_ENV}=1 with docker available; runs containers",
)


@pytest.fixture(scope="module", autouse=True)
def proxy() -> None:
    # Only the proxy: the probes need no database, queue or gateway.
    subprocess.run(["docker", "compose", "up", "-d", PROXY_SERVICE], check=True, timeout=PROBE_TIMEOUT_S)


def run_in_worker(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", "run", "--rm", "--no-deps", SERVICE, *command],
        capture_output=True,
        text=True,
        timeout=PROBE_TIMEOUT_S,
    )


WRITE_ONLY_TMP = dedent("""
    from pathlib import Path
    Path('/tmp/probe').write_text('ok')
    try:
        Path('/srv/probe').write_text('bad')
    except OSError:
        pass
    else:
        raise SystemExit('wrote outside tmpfs')
""")
NOT_ROOT = dedent("""
    import os
    assert os.getuid() != 0, 'running as root'
    try:
        os.setuid(0)
    except PermissionError:
        pass
    else:
        raise SystemExit('became root')
""")
PROXY_DENIES_OTHER_HOSTS = dedent("""
    import urllib.request
    try:
        urllib.request.urlopen('https://example.com', timeout=10)
    except OSError:
        pass
    else:
        raise SystemExit('reached example.com')
""")
NO_DIRECT_ROUTE = dedent("""
    import socket
    try:
        socket.create_connection(('1.1.1.1', 443), timeout=5)
    except OSError:
        pass
    else:
        raise SystemExit('connected without the proxy')
""")


@pytest.mark.parametrize(
    "command",
    [
        ["python", "-c", WRITE_ONLY_TMP],
        ["python", "-c", NOT_ROOT],
        ["python", "-c", PROXY_DENIES_OTHER_HOSTS],
        ["python", "-c", NO_DIRECT_ROUTE],
        ["git", "ls-remote", "https://github.com/git/git", "HEAD"],
    ],
    ids=["writes-only-tmp", "not-root", "proxy-denies-other-hosts", "no-direct-route", "git-host-allowed"],
)
def test_probe_passes_inside_the_worker(command: list[str]) -> None:
    result = run_in_worker(command)
    assert result.returncode == 0, result.stderr


def test_git_refuses_non_https_protocols() -> None:
    result = run_in_worker(["git", "ls-remote", "git://github.com/git/git"])
    assert result.returncode != 0
    assert "transport 'git' not allowed" in result.stderr
