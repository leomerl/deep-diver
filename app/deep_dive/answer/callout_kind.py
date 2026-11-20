from enum import StrEnum


class CalloutKind(StrEnum):
    tip = "tip"  # what to say or default to in an interview
    info = "info"  # nuance, a common misconception, or how deep each level needs to go
    warning = "warning"  # an anti-pattern or a way to lose data
