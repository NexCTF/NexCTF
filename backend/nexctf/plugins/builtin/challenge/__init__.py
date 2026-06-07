from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge
from nexctf.plugins.builtin.challenge.standard.schema import (
    StandardChallengeCreate,
    StandardChallengeRead,
    StandardChallengeUpdate,
)
from nexctf.plugins.registry import challenge_registry

challenge_registry.register(
    "standard",
    model=StandardChallenge,
    create_schema=StandardChallengeCreate,
    update_schema=StandardChallengeUpdate,
    read_schema=StandardChallengeRead,
)
