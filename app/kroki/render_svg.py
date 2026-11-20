import httpx

from .diagram_language import DiagramLanguage
from .diagram_syntax_error import DiagramSyntaxError


def render_svg(client: httpx.Client, language: DiagramLanguage, source: str) -> str:
    """The diagram as an SVG document. `client` carries Kroki's base URL and the timeout.

    Raises DiagramSyntaxError when Kroki rejects the source, httpx.HTTPError when Kroki is down or failing."""
    response = client.post(f"/{language}/svg", content=source.encode(), headers={"Content-Type": "text/plain"})
    if response.status_code == httpx.codes.BAD_REQUEST:
        raise DiagramSyntaxError(response.text.strip())
    response.raise_for_status()
    return response.text
