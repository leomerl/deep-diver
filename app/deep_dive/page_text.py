import re
from html.parser import HTMLParser

SKIPPED_TAGS = frozenset({"head", "script", "style", "svg"})  # styling and diagrams: markup, not prose
LINE_NUMBER_CLASS = "ln"  # the excerpt gutter (deep_dive.html.j2); kept, it would fuse into each code line
BLOCK_TAGS = frozenset({"br", "div", "figcaption", "h1", "h2", "h3", "h4", "li", "p", "pre", "section", "tr"})
BLANK_RUNS = re.compile(r"\n\s*\n+")


def page_text(html: str) -> str:
    """A rendered deep dive page as the reader sees its text: headings, prose, captions and code, one block per
    line. Only our own template goes through here, so the parser can rely on its shape."""
    parser = _PageText()
    parser.feed(html)
    parser.close()
    return BLANK_RUNS.sub("\n\n", "".join(parser.parts)).strip()


class _PageText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skipping = 0
        self.in_line_number = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIPPED_TAGS:
            self.skipping += 1
        elif tag == "span" and ("class", LINE_NUMBER_CLASS) in attrs:
            self.in_line_number = True  # holds only the number, so the next </span> closes it
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIPPED_TAGS:
            self.skipping -= 1
        elif tag == "span":
            self.in_line_number = False
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skipping and not self.in_line_number:
            self.parts.append(data)
