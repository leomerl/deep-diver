"""Messages both agent runtimes send the model when a turn brings no usable answer."""

MAX_ANSWER_ATTEMPTS = 2  # the first answer plus one retry with the validation error fed back
NUDGE = "Keep exploring with the tools if you need to, then give your final answer by calling {answer}."
REJECTED = "Answer rejected. Fix these problems and call {answer} again:\n{errors}"
WRAP_UP = (
    "You have used your exploration budget. You have {turns} more turns: stop exploring and call {answer} "
    "with your best answer now."
)
