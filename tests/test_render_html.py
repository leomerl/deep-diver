import base64
from pathlib import Path

import pytest

from app.deep_dive.answer import AnswerContext, DeepDiveAnswer
from app.deep_dive.render_html import highlight_lines, reading_minutes, render_html
from app.workspace import Workspace

SVG = '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
DRAWN = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 4 4"><rect width="4" height="4"/></svg>'


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    (tmp_path / "queue.py").write_text("import redis\nif a < b:\n    enqueue()\n")
    return Workspace(root=tmp_path, files=frozenset({"queue.py"}))


def _context(workspace: Workspace) -> AnswerContext:
    return AnswerContext(workspace, lambda language, source: SVG)


TECH = {
    "name": "Redis Streams", "role": "Holds queued jobs.", "pros": ["Consumer groups track who took what."],
    "cons": ["Memory bound."], "alternatives": [{"name": "Kafka", "trade_off": "Replay, but heavy to run."}],
    "fit": "Redis is already the cache.",
}
QUESTIONS = [
    {"question": "Why use `XACK`?", "answer": "So a crash redelivers.\n\nWithout it, jobs are lost."},
    {"question": "Why Redis?", "answer": "It is already running."},
    {"question": "What breaks?", "answer": "Duplicate jobs."},
]


def _answer(workspace: Workspace, text: str, tech_stack: list[dict[str, object]] | None = None) -> DeepDiveAnswer:
    return DeepDiveAnswer.model_validate({
        "tech_stack": tech_stack or [],
        "interview_questions": QUESTIONS,
        "title": "The queue",
        "sections": [{"heading": "How `enqueue` works", "blocks": [
            {"type": "paragraph", "text": text},
            {"type": "callout", "kind": "warning", "text": "Retries can duplicate jobs."},
            {"type": "code", "path": "queue.py", "start_line": 2, "end_line": 3, "caption": "The guard"},
            {"type": "diagram", "language": "mermaid", "source": "graph TD; a-->b", "caption": "The `enqueue` path"},
            {"type": "svg", "svg": DRAWN, "caption": "The buffer"},
        ]}],
    }, context=_context(workspace))


def _render(workspace: Workspace, text: str, tech_stack: list[dict[str, object]] | None = None) -> str:
    return render_html(_answer(workspace, text, tech_stack), workspace)


def test_model_text_is_escaped_and_backticks_become_code(workspace: Workspace) -> None:
    html = _render(workspace, "Calls `run()` <script>alert(1)</script>")

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<code>run()</code>" in html
    assert "<h2>How <code>enqueue</code> works</h2>" in html


def test_excerpt_copies_real_lines_highlighted_and_escaped_with_line_numbers(workspace: Workspace) -> None:
    html = _render(workspace, "Text.")

    assert '<span class="ln">2</span><span class="k">if</span>' in html
    assert '<span class="o">&lt;</span>' in html
    assert '<span class="ln">3</span>' in html and "enqueue" in html
    assert "redis" not in html


def test_highlighting_keeps_line_numbers_and_closes_spans_per_line() -> None:
    lines = highlight_lines('\n\n"""one\ntwo"""\nx = 1\n', "a.py")

    assert lines[2].startswith("<span") and lines[2].endswith("</span>")  # docstring split cleanly across lines
    assert "two" in lines[3]
    assert "x" in lines[4]


def test_unknown_file_type_is_escaped_plain_text() -> None:
    assert highlight_lines("a <b>", "notes.unknownext")[0] == "a &lt;b&gt;"


def test_diagram_is_an_image_with_the_caption_as_alt_text(workspace: Workspace) -> None:
    html = _render(workspace, "Text.")

    assert '<img src="data:image/svg+xml;base64,' + base64.b64encode(SVG.encode()).decode() in html
    assert 'alt="The `enqueue` path"' in html
    assert "<figcaption>The <code>enqueue</code> path</figcaption>" in html
    assert "<script>" not in html  # the SVG travels as base64 inside an attribute, never as markup


def test_hand_drawn_svg_figure_renders_like_a_diagram(workspace: Workspace) -> None:
    html = _render(workspace, "Text.")

    assert html.count('<figure class="diagram">') == 2
    assert base64.b64encode(DRAWN.encode()).decode() in html
    assert "2 figures" in html


def test_callout_carries_its_kind(workspace: Workspace) -> None:
    html = _render(workspace, "Text.")
    assert '<aside class="callout warning">' in html
    assert '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">' in html  # decorative; the label says "Watch out"


def test_tech_stack_renders_only_when_present(workspace: Workspace) -> None:
    assert "Tech stack" not in _render(workspace, "Text.")

    html = _render(workspace, "Text.", [TECH])
    assert "<h3>Redis Streams</h3>" in html
    assert "<dt>Kafka</dt><dd>Replay, but heavy to run.</dd>" in html
    assert "<p>Redis is already the cache.</p>" in html


def test_interview_questions_render_as_closed_details_one_paragraph_per_block(workspace: Workspace) -> None:
    html = _render(workspace, "Text.")

    assert html.count("<details><summary>Show answer</summary>") == len(QUESTIONS)
    assert "<details open" not in html
    assert "<h3>Why use <code>XACK</code>?</h3>" in html
    assert "<p>So a crash redelivers.</p>\n<p>Without it, jobs are lost.</p>" in html


def test_reading_time_counts_prose_words(workspace: Workspace) -> None:
    assert reading_minutes(_answer(workspace, "word " * 10)) == 1
    assert reading_minutes(_answer(workspace, "word " * 850)) == 5  # within MAX_PROSE_WORDS
    assert "5 min read" in _render(workspace, "word " * 850)
