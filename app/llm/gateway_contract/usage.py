from pydantic import BaseModel


class Usage(BaseModel):
    input_tokens: int  # every input token the model read, cached or not
    output_tokens: int
    # The cached parts of input_tokens, billed differently (reads far cheaper, writes a little dearer).
    # Default 0 so an older gateway or client still parses.
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
