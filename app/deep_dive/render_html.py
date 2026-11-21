import base64
import math
import re
from functools import cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from markupsafe import Markup, escape
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_for_filename
from pygments.lexers.special import TextLexer
from pygments.util import ClassNotFound

from app.workspace import Workspace

from .answer import Callout, CodeExcerpt, DeepDiveAnswer, Paragraph
from .content_security_policy import HTML_CSP
from .icon_paths import ICON_PATHS
from .xcode_dark_style import XcodeDarkStyle

INLINE_CODE = re.compile(r"`([^`]+)`")
PARAGRAPH_BREAK = re.compile(r"\n\s*\n")
TEMPLATE = "deep_dive.html.j2"
CSS_TEMPLATE = "deep_dive.css.j2"
# Technical prose is read slower than the ~240 wpm of light reading.
WORDS_PER_MINUTE = 200
LIGHT_CODE_STYLE = "xcode"
_FORMATTER = HtmlFormatter(style=XcodeDarkStyle, nowrap=True)
# Token colours only, scoped to code panels; Pygments' unscoped `pre` rules would restyle the whole page.
# Both palettes share Pygments' token classes, so one highlighted page carries both and the theme picks.
CODE_CSS = Markup(
    "\n".join(HtmlFormatter(style=LIGHT_CODE_STYLE).get_token_style_defs(".code pre"))
    + "\n@media (prefers-color-scheme: dark) {\n"
    + "\n".join(_FORMATTER.get_token_style_defs(".code pre"))
    + "\n}"
)


def render_html(answer: DeepDiveAnswer, workspace: Workspace) -> str:
    """The answer as one self-contained HTML page. Code excerpts are copied from the checkout, so run it before the
    checkout is deleted."""

    @cache
    def highlighted_lines(path: str) -> list[Markup]:
        source = workspace.file_path(path).read_text(encoding="utf-8", errors="replace")
        return highlight_lines(source, Path(path).name)

    def excerpt_lines(block: CodeExcerpt) -> list[tuple[int, Markup]]:
        lines = highlighted_lines(block.path)
        return list(enumerate(lines[block.start_line - 1:block.end_line], block.start_line))

    return _ENV.get_template(TEMPLATE).render(
        answer=answer, excerpt_lines=excerpt_lines, csp=HTML_CSP, code_css=CODE_CSS,
        reading_minutes=reading_minutes(answer),
    )


def page_css() -> str:
    """The page's stylesheet, as render_html inlines it."""
    return _ENV.get_template(CSS_TEMPLATE).render(code_css=CODE_CSS)


def highlight_lines(source: str, filename: str) -> list[Markup]:
    """One HTML line per source line. The whole file is lexed, not just the excerpt: an excerpt that starts inside a
    docstring would otherwise be coloured as code."""
    try:
        lexer = get_lexer_for_filename(filename, stripnl=False)
    except ClassNotFound:
        lexer = TextLexer(stripnl=False)
    # stripnl=False: stripping leading blank lines would shift every line number.
    # Pygments escapes token text and closes each span at the end of its line, so splitting on "\n" keeps both safe.
    return [Markup(line) for line in highlight(source, lexer, _FORMATTER).split("\n")]


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


def icon(name: str) -> Markup:
    """An outline icon from ICON_PATHS. Decorative: the text beside it carries the meaning."""
    return Markup(f'<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="{ICON_PATHS[name]}"/></svg>')


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
_ENV.globals["icon"] = icon
