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


class ClientSource(str, Enum):
    """How a request authenticated: browser cookie or API token."""

    cookie = "cookie"
    token = "token"


class ClientCategory(str, Enum):
    """What kind of client a user-agent belongs to."""

    AI = "ai"
    AUTOMATION = "automation"
    BROWSER = "browser"
