import re
from typing import Annotated

from pydantic import AfterValidator

from app.deep_dive.humanizer_rules import BANNED_DASHES, BANNED_PHRASES, BANNED_WORDS

INLINE_CODE = re.compile(r"`[^`]*`")  # identifiers in code may legitimately contain a banned word
BANNED = re.compile(r"\b(" + "|".join(map(re.escape, (*BANNED_WORDS, *BANNED_PHRASES))) + r")\b", re.IGNORECASE)


def check_prose(text: str) -> str:
    """Reject text with humanizer tells, listing every hit at once so one retry can fix them all."""
    prose = INLINE_CODE.sub("", text)
    hits = [*(repr(dash) for dash in BANNED_DASHES if dash in prose), *(m.group(0) for m in BANNED.finditer(prose))]
    if hits:
        raise ValueError(f"remove AI-writing tells: {', '.join(hits)}. Use a period, comma or colon instead of a dash")
    return text


Prose = Annotated[str, AfterValidator(check_prose)]
