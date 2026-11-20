# Headings that name a template slot instead of what this area does. Exact matches only (after casefold and
# trimming), so "What breaks when keys leak" passes: a false rejection costs the agent its one retry.
GENERIC_HEADINGS = frozenset({
    "overview", "introduction", "opening", "worked example", "core concepts", "how it works", "what breaks",
    "design choices", "what this area does", "failure modes", "trade-offs", "tradeoffs",
})

# A heading starting with one of these is the closing summary; only the last section may have it.
SUMMARY_PREFIXES = ("summary", "overview")
