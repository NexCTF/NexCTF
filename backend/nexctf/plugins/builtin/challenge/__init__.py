from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge
from nexctf.plugins.builtin.challenge.standard.schema import (
    StandardChallengeCreate,
    StandardChallengeRead,
    StandardChallengeUpdate,
)
from nexctf.plugins.declare import Plugin, TypeDef

plugin = Plugin(
    challenge_types=[
        TypeDef(
            "standard",
            model=StandardChallenge,
            create_schema=StandardChallengeCreate,
            update_schema=StandardChallengeUpdate,
            read_schema=StandardChallengeRead,
        ),
    ],
)
