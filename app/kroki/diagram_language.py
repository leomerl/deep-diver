from enum import StrEnum


class DiagramLanguage(StrEnum):
    """Kroki's name for each language we render; the value is the first segment of the request path."""
    graphviz = "graphviz"
    mermaid = "mermaid"
