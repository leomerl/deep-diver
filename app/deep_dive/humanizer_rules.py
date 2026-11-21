"""Mechanical subset of the humanizer rules (github.com/blader/humanizer, v4).

Only tells that are wrong in almost every context go here: a false hit rejects the agent's answer, and two
rejections fail the deep dive. Context-dependent rules (sentence-case headings, triads, closers) live in the prompt.
Words with technical meanings (key, robust, gate, highlight) are left out on purpose.
"""

BANNED_DASHES = ("—", "–", " -- ")

BANNED_WORDS = (
    "actually", "additionally", "bolstered", "crucial", "delve", "enduring", "enhance", "garner", "interplay",
    "intricate", "intricacies", "landscape", "meticulous", "meticulously", "pivotal", "quietly", "showcase",
    "tapestry", "testament", "underscore", "underscores", "valuable", "vibrant",
)  # not "deep dive": it is this product's name, so every page has to say it

BANNED_PHRASES = (
    # staged run-ups
    "let's dive in", "let's explore", "let's break this down", "here's what you need to know",
    "without further ado", "here's the thing", "the thing is", "let's be honest", "real talk",
    # sayings that sound deep
    "at its core", "the real question is", "what really matters", "the heart of the matter", "the deeper issue",
    # closers
    "let that sink in", "read that again", "that distinction matters",
    # arguing with no one
    "don't get me wrong", "this is not to say", "one might be tempted to",
    # inflated significance
    "stands as a testament", "plays a key role", "setting the stage for", "reflects a broader",
    "evolving landscape", "the future looks bright",
    # chatbot residue
    "i hope this helps", "great question", "let me know", "would you like",
)
