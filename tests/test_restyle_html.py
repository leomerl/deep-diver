from pathlib import Path

import pytest

from app.deep_dive.answer import AnswerContext, DeepDiveAnswer
from app.deep_dive.render_html import icon, page_css, render_html
from app.deep_dive.restyle_html import restyle_html
from app.workspace import Workspace

SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 4 4"><rect width="4" height="4"/></svg>'
# Trimmed from a page rendered by the previous template.
OLD_PAGE = """<html><head>
<style>
  body { color: red; }
</style>
</head><body>
<header>
<p class="eyebrow">Deep dive</p>
<h1>The queue</h1>
<p class="meta">3 min read · 2 sections · 1 code excerpt · 0 figures</p>
</header>
<figure class="code">
<figcaption><code class="where">app/queue.py:2-4</code><span>The <code>guard</code></span></figcaption>
<pre tabindex="0"><code><span class="ln">2</span>if a &lt; b:
<span class="ln">3</span>
<span class="ln">4</span>    enqueue()
</code></pre>
</figure>
<aside class="callout tip"><p class="callout-label"><span class="icon" aria-hidden="true">✓</span>Interview tip</p></aside>
<section class="summary">
<p class="eyebrow">Key takeaways</p>
</section>
</body></html>"""


def test_old_page_gets_current_css_markup_and_colours() -> None:
    page = restyle_html(OLD_PAGE)

    assert page_css() in page and "color: red" not in page
    assert "eyebrow" not in page
    assert '<ul class="meta" aria-label="About this deep dive"><li>3 min read</li><li>2 sections</li>' in page
    assert '<p class="summary-label">Key takeaways</p>' in page
    assert f'<p class="callout-label">{icon("tip")}Interview tip</p>' in page
    assert '<code class="where">app/queue.py<span class="lines">:2-4</span></code>' in page
    assert '<span class="caption">The <code>guard</code></span>' in page
    assert '<span class="ln">2</span><span class="k">if</span>' in page
    assert '<span class="o">&lt;</span>' in page
    assert '<span class="ln">3</span>\n<span class="ln">4</span>' in page  # blank line keeps its number


def test_unrecognised_code_figure_fails_instead_of_half_converting() -> None:
    broken = OLD_PAGE.replace('<code class="where">', '<code class="somewhere">')

    with pytest.raises(ValueError, match="not in the expected format"):
        restyle_html(broken)


def test_current_page_is_unchanged(tmp_path: Path) -> None:
    (tmp_path / "queue.py").write_text("import redis\nif a < b:\n    enqueue()\n")
    workspace = Workspace(root=tmp_path, files=frozenset({"queue.py"}))
    answer = DeepDiveAnswer.model_validate({
        "tech_stack": [], "title": "The queue",
        "interview_questions": [{"question": f"Question {n}?", "answer": "Because."} for n in range(3)],
        "sections": [
            {"heading": "The `enqueue` guard", "blocks": [
                {"type": "code", "path": "queue.py", "start_line": 2, "end_line": 3, "caption": "The guard"},
                {"type": "svg", "svg": SVG, "caption": "The buffer"},
            ]},
            {"heading": "Wrap-up", "blocks": [{"type": "paragraph", "text": "Done."}]},
        ],
    }, context=AnswerContext(workspace, lambda language, source: ""))
    page = render_html(answer, workspace)

    assert restyle_html(page) == page
