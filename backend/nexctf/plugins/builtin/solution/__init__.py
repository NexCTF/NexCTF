from nexctf.enums import InputType
from nexctf.plugins.builtin.solution.match.model import MatchSolution
from nexctf.plugins.builtin.solution.match.schema import (
    MatchSolutionCreate,
    MatchSolutionRead,
    MatchSolutionUpdate,
)
from nexctf.plugins.builtin.solution.mcq.model import MCQSolution
from nexctf.plugins.builtin.solution.mcq.schema import (
    MCQSolutionCreate,
    MCQSolutionRead,
    MCQSolutionUpdate,
)
from nexctf.plugins.builtin.solution.regex.model import RegexSolution
from nexctf.plugins.builtin.solution.regex.schema import (
    RegexSolutionCreate,
    RegexSolutionRead,
    RegexSolutionUpdate,
)
from nexctf.plugins.registry import solution_registry

solution_registry.register(
    "match",
    model=MatchSolution,
    create_schema=MatchSolutionCreate,
    update_schema=MatchSolutionUpdate,
    read_schema=MatchSolutionRead,
    compatible_input_types=[InputType.INPUT, InputType.TEXT, InputType.CODE],
    description="Exact match — the submitted answer must equal the expected flag (case-insensitive strip).",
)

solution_registry.register(
    "regex",
    model=RegexSolution,
    create_schema=RegexSolutionCreate,
    update_schema=RegexSolutionUpdate,
    read_schema=RegexSolutionRead,
    compatible_input_types=[InputType.INPUT, InputType.TEXT, InputType.CODE],
    description="Regex match — the submitted answer must match a regular expression pattern.",
)

solution_registry.register(
    "mcq",
    model=MCQSolution,
    create_schema=MCQSolutionCreate,
    update_schema=MCQSolutionUpdate,
    read_schema=MCQSolutionRead,
    compatible_input_types=[InputType.MCQ],
    description="Multiple choice — player picks one option from a shuffled list of correct and distractor answers.",
)
