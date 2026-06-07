from enum import Enum


class InputType(str, Enum):
    INPUT = "input"
    CODE = "code"
    TEXT = "text"
    MCQ = "mcq"
