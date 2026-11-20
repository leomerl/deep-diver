from pydantic import BaseModel, Field


class Correction(BaseModel):
    """One claim the verifier changed. Logged, not rendered: it is how we see what verification catches."""
    claim: str = Field(description="The original sentence or phrase, quoted.")
    problem: str = Field(description="contradicted or unsupported, and what the code actually does.")
    evidence: str = Field(description="path:start-end of the lines that settle it.")
