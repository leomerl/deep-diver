from pygments.style import Style
from pygments.token import (
    Comment, Error, Keyword, Name, Number, Operator, Punctuation, String, Text, Token,
)


class XcodeDarkStyle(Style):
    """Token colours modelled on Xcode's Default (Dark) theme. Pygments' own `xcode` style is light-only, and the
    code panels stay dark in both page themes. Comments are lifted from Xcode's #6c7986 (3.7:1 on the panel) to
    #848f9b (5.0:1) to pass 4.5:1."""

    background_color = "#1f1f24"
    styles = {
        Token: "#dfdfe0",
        Text: "#dfdfe0",
        Comment: "#848f9b",
        Comment.Preproc: "#fd8f3f",
        Keyword: "bold #fc5fa3",
        Keyword.Type: "#d0a8ff",
        Name.Builtin: "#d0a8ff",
        Name.Class: "#5dd8ff",
        Name.Function: "#4eb0cc",
        Name.Decorator: "#cc9768",
        Name.Attribute: "#cc9768",
        Name.Tag: "#fc5fa3",
        Name.Exception: "#d0a8ff",
        String: "#fc6a5d",
        String.Escape: "#d0bf69",
        Number: "#d0bf69",
        Operator: "#dfdfe0",
        Operator.Word: "bold #fc5fa3",
        Punctuation: "#dfdfe0",
        Error: "#fc6a5d",
    }
