class DiagramSyntaxError(ValueError):
    """Kroki rejected the source. Separate from HTTP errors: the author can fix this one, a down service they can't."""
