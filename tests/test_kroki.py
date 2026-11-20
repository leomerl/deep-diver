import httpx
import pytest

from app.kroki import DiagramLanguage, DiagramSyntaxError, render_svg

SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"></svg>'


def client_returning(status: int, text: str, seen: list[httpx.Request]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, text=text)

    return httpx.Client(base_url="http://kroki", transport=httpx.MockTransport(handler))


def test_posts_source_to_language_path_and_returns_svg() -> None:
    seen: list[httpx.Request] = []
    svg = render_svg(client_returning(200, SVG, seen), DiagramLanguage.mermaid, "graph TD; A-->B")
    assert svg == SVG
    assert seen[0].url == "http://kroki/mermaid/svg"
    assert seen[0].content == b"graph TD; A-->B"


def test_bad_source_raises_syntax_error_with_krokis_message() -> None:
    client = client_returning(400, "Error 400: syntax error in line 1\n", [])
    with pytest.raises(DiagramSyntaxError, match="syntax error in line 1"):
        render_svg(client, DiagramLanguage.graphviz, "digraph {")


def test_server_failure_is_not_a_syntax_error() -> None:
    with pytest.raises(httpx.HTTPStatusError):
        render_svg(client_returning(503, "unavailable", []), DiagramLanguage.graphviz, "digraph { a -> b }")
