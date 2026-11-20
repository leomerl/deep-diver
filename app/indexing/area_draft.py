from langchain_core.tools import ToolException
from pydantic import BaseModel, Field, ValidationInfo, field_validator

from app.workspace import Workspace


class AreaDraft(BaseModel):
    """One area: a part of the code a developer would think of as one thing."""

    name: str = Field(description="Short name a developer would use, e.g. 'Auth' or 'Job queue'.")
    description: str = Field(description="One or two sentences: what this area does and why it exists.")
    paths: list[str] = Field(
        description="Folders (preferred) or files, relative to the repo root, that make up this area."
    )

    @field_validator("name", "description")
    @classmethod
    def _not_blank(cls, text: str) -> str:
        if not text.strip():
            raise ValueError("must not be blank")
        return text.strip()

    @field_validator("paths")
    @classmethod
    def _real_and_in_scope(cls, paths: list[str], info: ValidationInfo) -> list[str]:
        """Checked against the agent's Workspace (passed as validation context): the real files and its scope."""
        workspace = _workspace(info)
        if not paths:
            raise ValueError("an area needs at least one path")
        problems = [problem for path in paths if (problem := _problem(workspace, path))]
        if problems:
            raise ValueError("; ".join(problems))
        # Stored normalized ("app/auth", never "./app/auth/"), so a deep dive's sparse checkout gets clean paths.
        return list(dict.fromkeys(workspace.normalize(path) for path in paths))


def _workspace(info: ValidationInfo) -> Workspace:
    if not isinstance(info.context, Workspace):
        raise TypeError("AreaDraft is validated with the agent's Workspace as context")
    return info.context


def _problem(workspace: Workspace, path: str) -> str | None:
    # files_under raises when a path is outside the scope or matches no file: exactly the two rules.
    try:
        workspace.files_under(path)
    except ToolException as e:
        return str(e)
    return None
