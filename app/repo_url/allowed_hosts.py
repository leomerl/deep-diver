# The worker runs `git clone` on these URLs; an open list would let users point it at internal hosts (SSRF).
ALLOWED_HOSTS: frozenset[str] = frozenset({
    "github.com",
    "gitlab.com",
    "bitbucket.org",
})
