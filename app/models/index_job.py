from .repo import RepoCreate


class IndexJob(RepoCreate):
    """The index job payload: the URL plus who added it, so the worker can clone with their GitHub token.

    Separate from RepoCreate on purpose: a client must not be able to pick whose token the worker uses.
    """

    user_id: int | None = None
