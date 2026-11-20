from pydantic import BaseModel


class GitHubRepo(BaseModel):
    full_name: str  # owner/name
    html_url: str  # what POST /repos takes
    private: bool
