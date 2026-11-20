from pathlib import Path

import pytest
from pydantic import ValidationError

from app.indexing.submit_areas import SubmitAreas
from app.workspace import Workspace

FILES = frozenset({"app/auth/login.py", "app/auth/session.py", "app/billing/pay.py", "README.md"})


def _validate(areas: list[dict[str, object]], scope: tuple[str, ...] = ()) -> SubmitAreas:
    workspace = Workspace(root=Path("."), files=FILES, scope=scope)
    return SubmitAreas.model_validate({"areas": areas}, context=workspace)


def _area(name: str, *paths: str) -> dict[str, object]:
    return {"name": name, "description": f"{name} things.", "paths": list(paths)}


def test_valid_answer_is_normalized() -> None:
    answer = _validate([_area(" Auth ", "./app/auth/", "app/auth"), _area("Billing", "app/billing/pay.py")])
    assert [(a.name, a.paths) for a in answer.areas] == [("Auth", ["app/auth"]), ("Billing", ["app/billing/pay.py"])]


@pytest.mark.parametrize(("areas", "scope", "message"), [
    ([_area("Auth", "src/auth")], (), "no files under 'src/auth'"),
    ([_area("Billing", "app/billing")], ("app/auth",), "outside your scope"),
    ([_area("Auth", "../etc")], (), "'..' is not allowed"),
    ([_area("Auth")], (), "at least one path"),
    ([_area("", "app/auth")], (), "must not be blank"),
    ([_area("Auth", "app/auth"), _area("auth", "app/billing")], (), "unique"),
    ([], (), "at least one area"),
    ([_area("Everything", "app/auth/login.py", "app/auth/session.py")], ("app/auth",), "covers your whole scope"),
])
def test_invalid_answers_are_rejected_with_a_message_the_model_can_act_on(
    areas: list[dict[str, object]], scope: tuple[str, ...], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        _validate(areas, scope)


def test_empty_list_means_leaf_below_the_top() -> None:
    assert _validate([], scope=("app/auth",)).areas == []
