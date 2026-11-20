import base64
import math
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from markupsafe import Markup, escape

from app.workspace import Workspace

from .answer import Callout, CodeExcerpt, DeepDiveAnswer, Paragraph
from .content_security_policy import HTML_CSP

INLINE_CODE = re.compile(r"`([^`]+)`")
PARAGRAPH_BREAK = re.compile(r"\n\s*\n")
TEMPLATE = "deep_dive.html.j2"
# Technical prose is read slower than the ~240 wpm of light reading.
WORDS_PER_MINUTE = 200


def render_html(answer: DeepDiveAnswer, workspace: Workspace) -> str:
    """The answer as one self-contained HTML page. Code excerpts are copied from the checkout, so run it before the
    checkout is deleted."""

    def excerpt_lines(block: CodeExcerpt) -> list[tuple[int, str]]:
        lines = workspace.file_path(block.path).read_text(encoding="utf-8", errors="replace").splitlines()
        return list(enumerate(lines[block.start_line - 1:block.end_line], block.start_line))

    return _ENV.get_template(TEMPLATE).render(
        answer=answer, excerpt_lines=excerpt_lines, csp=HTML_CSP, reading_minutes=reading_minutes(answer)
    )


def reading_minutes(answer: DeepDiveAnswer) -> int:
    """Prose only; code excerpts are studied, not read, so a word count says nothing about them."""
    texts = [
        answer.title,
        *(section.heading for section in answer.sections),
        *(block.text if isinstance(block, Paragraph | Callout) else block.caption
          for section in answer.sections for block in section.blocks),
        *(text for tech in answer.tech_stack for text in (
            tech.name, tech.role, tech.fit, *tech.pros, *tech.cons,
            *(part for alt in tech.alternatives for part in (alt.name, alt.trade_off)),
        )),
        *(text for item in answer.interview_questions for text in (item.question, item.answer)),
    ]
    return max(1, math.ceil(sum(len(text.split()) for text in texts) / WORDS_PER_MINUTE))


def _paragraphs(text: str) -> list[str]:
    return [part for part in PARAGRAPH_BREAK.split(text.strip()) if part]


def _inline_code(text: str) -> Markup:
    # Escape first, then add <code>: the only markup in the output is markup we wrote.
    return Markup(INLINE_CODE.sub(r"<code>\1</code>", str(escape(text))))


def _svg_data_uri(svg: str) -> str:
    # Shown through <img>: the browser runs no script and fetches nothing from an SVG image, however hostile.
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


# autoescape: model text and repo code are untrusted; a `<script>` in either must render as text.
_ENV = Environment(
    loader=FileSystemLoader(Path(__file__).with_name("templates")), autoescape=True, undefined=StrictUndefined
)
_ENV.filters["inline_code"] = _inline_code
_ENV.filters["paragraphs"] = _paragraphs
_ENV.filters["svg_data_uri"] = _svg_data_uri
