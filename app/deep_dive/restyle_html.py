import html
import re
from pathlib import PurePosixPath

from .render_html import highlight_lines, icon, page_css

# Each pattern matches markup that render_html wrote in an earlier version of the template, so the format is known.
STYLE = re.compile(r"(<style>\n).*?(</style>)", re.S)
EYEBROW = '<p class="eyebrow">Deep dive</p>\n'
META = re.compile(r'<p class="meta">(.*?)</p>')
META_SEPARATOR = " · "
TAKEAWAYS = '<p class="eyebrow">Key takeaways</p>'
CODE_FIGURE = re.compile(
    r'<figcaption><code class="where">(?P<path>[^<]*):(?P<lines>\d+-\d+)</code><span>(?P<caption>.*?)</span></figcaption>\n'
    r'<pre tabindex="0"><code>(?P<body>.*?)</code></pre>',
    re.S,
)
NUMBERED_LINE = re.compile(r'<span class="ln">(\d+)</span>(.*)')
FIGURE_TAG = '<figure class="code">'
GLYPH_ICON = re.compile(r'<span class="icon" aria-hidden="true">([^<])</span>')
GLYPH_ICON_NAMES = {"✓": "tip", "i": "info", "!": "warning", "+": "plus", "−": "minus"}


def restyle_html(page: str) -> str:
    """An old deep dive page with the current stylesheet and markup. A current page comes back unchanged."""
    page = STYLE.sub(lambda m: m[1] + page_css() + "\n" + m[2], page, count=1)
    page = page.replace(EYEBROW, "").replace(TAKEAWAYS, '<p class="summary-label">Key takeaways</p>')
    page = META.sub(_meta, page, count=1)
    page = GLYPH_ICON.sub(lambda m: icon(GLYPH_ICON_NAMES[m[1]]), page)
    page, converted = CODE_FIGURE.subn(_code_figure, page)
    old_figures = page.count(FIGURE_TAG) - page.count('<span class="lines">')
    if old_figures:
        # A half-converted page would look broken; fail so the stored page is left as it was.
        raise ValueError(f"{old_figures} code figure(s) not in the expected format ({converted} converted)")
    return page


def _meta(match: re.Match[str]) -> str:
    items = "".join(f"<li>{part}</li>" for part in match[1].split(META_SEPARATOR))
    return f'<ul class="meta" aria-label="About this deep dive">{items}</ul>'


def _code_figure(match: re.Match[str]) -> str:
    numbered = [NUMBERED_LINE.fullmatch(line) for line in match["body"].split("\n") if line]
    if not all(numbered):
        raise ValueError(f"unexpected excerpt line in {match['path']}")
    source = "\n".join(html.unescape(m[2]) for m in numbered if m)
    # shortcut: lexes the excerpt alone (the checkout is gone), so one starting mid-docstring is coloured as code;
    # regenerate that deep dive if it matters.
    lines = highlight_lines(source, PurePosixPath(html.unescape(match["path"])).name)
    body = "".join(f'<span class="ln">{m[1]}</span>{line}\n' for m, line in zip(numbered, lines) if m)
    return (
        f'<figcaption><code class="where">{match["path"]}<span class="lines">:{match["lines"]}</span></code>'
        f'<span class="caption">{match["caption"]}</span></figcaption>\n'
        f'<pre tabindex="0"><code>{body}</code></pre>'
    )
