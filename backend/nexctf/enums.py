from enum import Enum


class InputType(str, Enum):
    INPUT = "input"
    CODE = "code"
    TEXT = "text"
    MCQ = "mcq"


class SessionWindow(str, Enum):
    """Time span the admin session pivot groups addresses over."""

    LIVE = "live"
    DAY = "day"
    ALL = "all"
