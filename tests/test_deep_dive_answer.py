from pathlib import Path

import pytest
from pydantic import ValidationError

from app.deep_dive.answer import MAX_CALLOUTS, MAX_EXCERPT_LINES, MAX_PROSE_WORDS, MAX_SECTIONS, MAX_SVG_BYTES, AnswerContext, DeepDiveAnswer, Diagram, SvgFigure
from app.kroki import DiagramLanguage, DiagramSyntaxError
from app.workspace import Workspace

SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"></svg>'
BAD_SOURCE = "digraph {"


def fake_render(language: DiagramLanguage, source: str) -> str:
    if source == BAD_SOURCE:
        raise DiagramSyntaxError("syntax error in line 1")
    return SVG


@pytest.fixture
def workspace(tmp_path: Path) -> AnswerContext:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "queue.py").write_text("\n".join(f"line {n}" for n in range(1, 101)))
    (tmp_path / "other.py").write_text("x = 1\n")
    checkout = Workspace(root=tmp_path, files=frozenset({"app/queue.py", "other.py"}), scope=("app",))
    return AnswerContext(checkout, fake_render)


QUESTIONS = [
    {"question": f"What happens on retry {n}?", "answer": f"It re-reads the stream.\n\nThen acks {n}."} for n in range(3)
]


def _answer(text: str = "Jobs go into one Redis stream.", **code: object) -> dict[str, object]:
    excerpt = {"type": "code", "path": "app/queue.py", "start_line": 1, "end_line": 10, "caption": "The enqueue"}
    return {
        "title": "The job queue",
        "interview_questions": QUESTIONS,
        "sections": [{
            "heading": "How a job moves",
            "blocks": [
                {"type": "paragraph", "text": text},
                {"type": "callout", "kind": "tip", "text": "Start with the dedup key."},
                excerpt | code,
                _diagram(),
            ],
        }],
    }


def _diagram(source: str = "digraph { a -> b }") -> dict[str, object]:
    return {"type": "diagram", "language": "graphviz", "source": source, "caption": "Who calls whom."}


def _section(heading: str, *blocks: dict[str, object]) -> dict[str, object]:
    return {"heading": heading, "blocks": [*blocks] or [{"type": "paragraph", "text": "Jobs go into one stream."}]}


def test_a_page_without_any_visual_is_rejected(workspace: AnswerContext) -> None:
    answer = _answer()
    answer["sections"] = [_section("How a job moves"), _section("The queue, in short")]
    with pytest.raises(ValidationError, match="no diagram or SVG figure"):
        _validate(answer, workspace)


def test_sections_without_a_visual_pass_when_the_page_has_enough(workspace: AnswerContext) -> None:
    answer = _answer()
    answer["sections"] = [
        _section("How a job moves", _diagram()),
        _section("Why the queue dedups by URL"),
        _section("The queue, in short"),
    ]
    _validate(answer, workspace)


def _validate(answer: dict[str, object], workspace: AnswerContext) -> DeepDiveAnswer:
    return DeepDiveAnswer.model_validate(answer, context=workspace)


def test_valid_answer_passes(workspace: AnswerContext) -> None:
    assert _validate(_answer(), workspace).sections[0].blocks[2].type == "code"


def test_em_dash_is_rejected(workspace: AnswerContext) -> None:
    with pytest.raises(ValidationError, match="remove AI-writing tells"):
        _validate(_answer("Jobs go into Redis — one stream."), workspace)


def test_every_banned_word_is_listed_in_one_error(workspace: AnswerContext) -> None:
    with pytest.raises(ValidationError) as e:
        _validate(_answer("This crucial queue plays a pivotal part."), workspace)
    assert "crucial" in str(e.value) and "pivotal" in str(e.value)


def test_banned_word_inside_inline_code_passes(workspace: AnswerContext) -> None:
    _validate(_answer("It calls `enhance_payload()` first."), workspace)


def test_excerpt_outside_scope_is_rejected(workspace: AnswerContext) -> None:
    with pytest.raises(ValidationError, match="not a file in your scope"):
        _validate(_answer(path="other.py", end_line=1), workspace)


def test_excerpt_past_end_of_file_is_rejected(workspace: AnswerContext) -> None:
    with pytest.raises(ValidationError, match="past the end"):
        _validate(_answer(start_line=95, end_line=101), workspace)


def test_too_long_excerpt_is_rejected(workspace: AnswerContext) -> None:
    with pytest.raises(ValidationError, match="longer than"):
        _validate(_answer(start_line=1, end_line=MAX_EXCERPT_LINES + 1), workspace)


def test_unknown_block_type_is_rejected(workspace: AnswerContext) -> None:
    answer = _answer()
    answer["sections"] = [{"heading": "Media", "blocks": [{"type": "video", "url": "x"}]}]
    with pytest.raises(ValidationError):
        _validate(answer, workspace)


def test_fewer_than_three_interview_questions_is_rejected(workspace: AnswerContext) -> None:
    answer = _answer()
    answer["interview_questions"] = QUESTIONS[:2]
    with pytest.raises(ValidationError, match="at least 3"):
        _validate(answer, workspace)


def test_tells_in_question_and_answer_are_listed_together(workspace: AnswerContext) -> None:
    answer = _answer()
    answer["interview_questions"] = [{"question": "Why is this crucial?", "answer": "It is pivotal."}, *QUESTIONS[1:]]
    with pytest.raises(ValidationError) as e:
        _validate(answer, workspace)
    assert "crucial" in str(e.value) and "pivotal" in str(e.value)


def test_diagram_is_rendered_while_validating(workspace: AnswerContext) -> None:
    answer = _answer()
    answer["sections"] = [{"heading": "Shape", "blocks": [_diagram()]}]
    block = _validate(answer, workspace).sections[0].blocks[0]
    assert isinstance(block, Diagram) and block.svg == SVG


def test_diagram_syntax_error_is_rejected_with_the_renderers_message(workspace: AnswerContext) -> None:
    answer = _answer()
    answer["sections"] = [{"heading": "Shape", "blocks": [_diagram(BAD_SOURCE)]}]
    with pytest.raises(ValidationError, match="graphviz rejected the diagram: syntax error in line 1"):
        _validate(answer, workspace)


def test_rendered_svg_is_not_part_of_the_tool_schema() -> None:
    assert "svg" not in Diagram.model_json_schema()["properties"]


def test_generic_heading_is_rejected_but_a_specific_one_passes(workspace: AnswerContext) -> None:
    answer = _answer()
    answer["sections"][0]["heading"] = "What breaks"  # type: ignore[index]  # test fixture is a plain dict
    with pytest.raises(ValidationError, match="generic heading"):
        _validate(answer, workspace)
    answer["sections"][0]["heading"] = "What breaks when the stream fills up"  # type: ignore[index]  # same
    _validate(answer, workspace)


def _figure(svg: str = SVG) -> dict[str, object]:
    return {"type": "svg", "svg": svg, "caption": "The ring buffer before and after a write."}


def _figure_answer(svg: str = SVG) -> dict[str, object]:
    answer = _answer()
    answer["sections"] = [{"heading": "The buffer layout", "blocks": [_figure(svg)]}]
    return answer


def test_well_formed_svg_figure_passes(workspace: AnswerContext) -> None:
    block = _validate(_figure_answer(), workspace).sections[0].blocks[0]
    assert isinstance(block, SvgFigure) and block.svg == SVG


@pytest.mark.parametrize(("svg", "problem"), [
    ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1 1'>", "not well-formed"),
    ("<div xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1 1'/>", "root element must be"),
    ("<svg viewBox='0 0 1 1'/>", "root element must be"),
    ("<svg xmlns='http://www.w3.org/2000/svg'/>", "needs a viewBox"),
    ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1 1'><script>alert(1)</script></svg>", "no <script>"),
    (SVG[:-6] + "<!--" + "x" * MAX_SVG_BYTES + "--></svg>", "over"),
])
def test_bad_svg_figure_is_rejected(workspace: AnswerContext, svg: str, problem: str) -> None:
    with pytest.raises(ValidationError, match=problem):
        _validate(_figure_answer(svg), workspace)


def test_summary_heading_is_allowed_only_on_the_last_section(workspace: AnswerContext) -> None:
    answer = _answer()
    body = answer["sections"][0]  # type: ignore[index]  # test fixture is a plain dict
    answer["sections"] = [{**body, "heading": "Summary of the queue"}, {**body, "heading": "Summary"}]
    with pytest.raises(ValidationError, match="only the last section may be a summary"):
        _validate(answer, workspace)
    answer["sections"] = [{**body, "heading": "How the queue hands out jobs"}, {**body, "heading": "Summary"}]
    _validate(answer, workspace)


CALLOUT = {"type": "callout", "kind": "tip", "text": "Start with the dedup key."}  # same as the one in _answer


def test_too_many_words_and_callouts_are_reported_together(workspace: AnswerContext) -> None:
    answer = _answer(" ".join(["word"] * MAX_PROSE_WORDS))  # plus the callout's words: just over the budget
    answer["sections"][0]["blocks"] += [CALLOUT] * MAX_CALLOUTS  # type: ignore[index]  # test fixture is a plain dict
    with pytest.raises(ValidationError, match=r"too long: \d+ words.*callouts"):
        _validate(answer, workspace)


def test_a_page_at_the_budget_passes(workspace: AnswerContext) -> None:
    callout_words = len(str(CALLOUT["text"]).split())
    _validate(_answer(" ".join(["word"] * (MAX_PROSE_WORDS - callout_words))), workspace)


def test_more_sections_than_the_cap_are_rejected(workspace: AnswerContext) -> None:
    answer = _answer()
    answer["sections"] = [_section("How a job moves", _diagram())] + [
        _section(f"Why the queue does thing {n}") for n in range(MAX_SECTIONS)
    ]
    with pytest.raises(ValidationError, match=f"at most {MAX_SECTIONS}"):
        _validate(answer, workspace)
