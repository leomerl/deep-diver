from .deep_dive import DeepDiveRead


class DeepDiveListItem(DeepDiveRead):
    """GET /deep-dives item: the deep dive plus the labels the list shows and groups by."""

    node_name: str | None  # None: the deep dive is about the whole repo
    repo_url: str
    stale: bool  # written from an older snapshot than the repo's current one
