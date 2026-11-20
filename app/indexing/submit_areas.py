from typing import Self

from pydantic import BaseModel, Field, ValidationInfo, model_validator

from app.workspace import Workspace

from .area_draft import AreaDraft

WHOLE_SCOPE = "."


class SubmitAreas(BaseModel):
    """Submit your final answer: the areas the code in your scope divides into.

    Return an empty list when your scope is one coherent area that shouldn't be split further.
    """

    areas: list[AreaDraft] = Field(description="The areas, each with a name, a description and its paths.")

    @model_validator(mode="after")
    def _a_real_split(self, info: ValidationInfo) -> Self:
        if not isinstance(info.context, Workspace):
            raise TypeError("SubmitAreas is validated with the agent's Workspace as context")
        workspace = info.context
        names = [area.name.casefold() for area in self.areas]
        if len(names) != len(set(names)):
            raise ValueError("area names must be unique")
        if not workspace.scope and not self.areas:
            raise ValueError("the repository needs at least one area")
        # An area holding everything its parent holds would be split again forever: each level must shrink.
        everything = set(workspace.files_under(WHOLE_SCOPE))
        too_big = [area.name for area in self.areas if _files(workspace, area) == everything]
        if workspace.scope and too_big:
            raise ValueError(f"{', '.join(too_big)} covers your whole scope; split it or return an empty list")
        return self


def _files(workspace: Workspace, area: AreaDraft) -> set[str]:
    return {file for path in area.paths for file in workspace.files_under(path)}
