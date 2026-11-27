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


class FileUsageKind(str, Enum):
    """Where a stored file is used: a link table or a text reference."""

    CHALLENGE = "challenge"
    QUESTION = "question"
    CHALLENGE_TEXT = "challenge_text"
    QUESTION_TEXT = "question_text"
    HINT_TEXT = "hint_text"
    PAGE_TEXT = "page_text"
    NOTIFICATION_TEXT = "notification_text"
    CONFIG = "config"


class FileUsageFilter(str, Enum):
    """Whether a file listing keeps the used or the unused files."""

    USED = "used"
    UNUSED = "unused"
