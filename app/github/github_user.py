from pydantic import BaseModel


class GitHubUser(BaseModel):
    """The fields of GET /user we keep; GitHub sends dozens more, which Pydantic ignores."""

    id: int
    login: str
