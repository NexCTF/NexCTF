from datetime import datetime, timedelta
from uuid import UUID

from fastapi_toolsets.fixtures import FixtureRegistry
from fastapi_toolsets.fixtures.enum import Context

from nexctf.model import (
    ChallengeCategory,
    Hint,
    HintUnlock,
    Question,
    ScoreAdjustment,
    Submission,
    Tag,
    Team,
    User,
    UserRole,
    UserToken,
)
from nexctf.plugins.builtin.challenge import StandardChallenge
from nexctf.plugins.builtin.solution.match.model import MatchSolution

_CTF_START = datetime.now() - timedelta(hours=1)


def _t(minutes: int) -> datetime:
    return _CTF_START + timedelta(minutes=minutes)


fixtures = FixtureRegistry(contexts=[Context.DEVELOPMENT])


@fixtures.register()
def challenge_category() -> list[ChallengeCategory]:
    return [
        ChallengeCategory(
            id=UUID("a5091be9-ce73-4f0e-be2c-0c2c475f4953"),
            slug="pentest",
            name="Pentest",
        ),
        ChallengeCategory(
            id=UUID("37e76635-fc50-4805-93f3-25e892185db3"),
            slug="re",
            name="Reverse Engineering",
        ),
        ChallengeCategory(
            id=UUID("7fc0d019-6c87-485f-8bb5-d9b5c8e4d63b"),
            slug="osint",
            name="OSINT",
        ),
        ChallengeCategory(
            id=UUID("f723e5cc-5fb4-42fb-9d56-04b043558fc7"),
            slug="cryptography",
            name="Cryptography",
        ),
        ChallengeCategory(
            id=UUID("6e3e76f4-37fd-47e2-9b8c-7fc055c68870"),
            slug="miscellaneous",
            name="Miscellaneous",
        ),
        ChallengeCategory(
            id=UUID("ff3c8389-eac0-42be-ba59-192b8990e62f"),
            slug="forensics",
            name="Forensics",
        ),
        ChallengeCategory(
            id=UUID("782fda72-aca1-4bc7-8ae8-2d7b2eedf4b0"),
            slug="networking",
            name="Networking",
        ),
    ]


@fixtures.register(depends_on=["challenge_category"])
def challenge() -> list[StandardChallenge]:
    def _catid(slug: str) -> UUID:
        return fixtures.field("challenge_category", "slug", slug)

    return [
        StandardChallenge(
            id=UUID("a1000000-0000-4000-8000-000000000001"),
            title="Web Basics",
            description="A beginner-friendly web challenge. Find the hidden flag on this simple site.",
            writeup=(
                "## Solution\n\n"
                "The flag for the first question is hidden in an HTML comment in the "
                "page source (`Ctrl+U` / View Page Source).\n\n"
                "The `/admin` path is protected by HTTP Basic Auth using the default "
                "credentials `admin:admin` — the second flag is on that page.\n\n"
                "```\n"
                "curl -u admin:admin https://target/admin\n"
                "```\n"
            ),
            is_active=True,
            category_id=_catid("pentest"),
        ),
        StandardChallenge(
            id=UUID("a1000000-0000-4000-8000-000000000002"),
            title="SQL Injection 101",
            description="Classic SQL injection — three stages, escalating difficulty.",
            is_active=True,
            sequential=True,
            category_id=_catid("pentest"),
        ),
        StandardChallenge(
            id=UUID("a1000000-0000-4000-8000-000000000003"),
            title="Binary Reversing",
            description="Reverse-engineer the binary to extract secrets hidden in the code.",
            is_active=True,
            category_id=_catid("re"),
        ),
        StandardChallenge(
            id=UUID("a1000000-0000-4000-8000-000000000004"),
            title="Caesar Cipher",
            description="Decrypt the intercepted ciphertext and identify the key.",
            is_active=True,
            category_id=_catid("cryptography"),
        ),
        StandardChallenge(
            id=UUID("a1000000-0000-4000-8000-000000000005"),
            title="OSINT Starter",
            description="Find the target using only open-source intelligence.",
            is_active=True,
            category_id=_catid("osint"),
        ),
        StandardChallenge(
            id=UUID("a1000000-0000-4000-8000-000000000006"),
            title="Misc Warmup",
            description="Miscellaneous warmup — read carefully.",
            is_active=False,
            category_id=_catid("miscellaneous"),
        ),
    ]


@fixtures.register(depends_on=["challenge"])
def question() -> list[Question]:
    def _cid(title: str) -> UUID:
        return fixtures.field("challenge", "title", title)

    return [
        # Web Basics — 2 questions
        Question(
            id=UUID("b1000000-0000-4000-8000-000000000001"),
            label="Find the hidden flag",
            description="Something is lurking in the page source...",
            index=0,
            points=100,
            malus=10,
            challenge_id=_cid("Web Basics"),
        ),
        Question(
            id=UUID("b1000000-0000-4000-8000-000000000008"),
            label="Bypass the HTTP auth",
            description="The /admin path is protected by HTTP Basic Auth. Bypass it.",
            index=1,
            points=150,
            malus=15,
            challenge_id=_cid("Web Basics"),
        ),
        # SQL Injection — 3 questions (sequential)
        Question(
            id=UUID("b1000000-0000-4000-8000-000000000002"),
            label="Bypass the login",
            description="The admin panel is protected. Can you get in without the password?",
            index=0,
            points=150,
            malus=15,
            challenge_id=_cid("SQL Injection 101"),
        ),
        Question(
            id=UUID("b1000000-0000-4000-8000-000000000003"),
            label="Extract the admin password",
            description="You're in. Now grab the admin hash from the database.",
            index=1,
            points=250,
            malus=25,
            challenge_id=_cid("SQL Injection 101"),
        ),
        Question(
            id=UUID("b1000000-0000-4000-8000-000000000009"),
            label="Read /etc/passwd",
            description="The database user has FILE privileges. Can you read the server's passwd file?",
            index=2,
            points=350,
            malus=35,
            challenge_id=_cid("SQL Injection 101"),
        ),
        # Binary Reversing — 3 questions
        Question(
            id=UUID("b1000000-0000-4000-8000-000000000004"),
            label="Find the license key",
            description="The binary checks a license key at startup. What is it?",
            index=0,
            points=200,
            malus=20,
            challenge_id=_cid("Binary Reversing"),
        ),
        Question(
            id=UUID("b1000000-0000-4000-8000-000000000010"),
            label="What is the hardcoded salt?",
            description="The binary hashes passwords before comparing them. What salt does it prepend?",
            index=1,
            points=275,
            malus=25,
            challenge_id=_cid("Binary Reversing"),
        ),
        Question(
            id=UUID("b1000000-0000-4000-8000-000000000011"),
            label="Patch the anti-debug check",
            description="Running under a debugger crashes the binary. Find the check and give the flag it hides.",
            index=2,
            points=400,
            malus=40,
            challenge_id=_cid("Binary Reversing"),
        ),
        # Caesar Cipher — 2 questions
        Question(
            id=UUID("b1000000-0000-4000-8000-000000000005"),
            label="Decrypt the message",
            description="Encrypted: 'arkpgs{whyvhf_j0hyq_or_cebhq}'",
            index=0,
            points=100,
            malus=10,
            challenge_id=_cid("Caesar Cipher"),
        ),
        Question(
            id=UUID("b1000000-0000-4000-8000-000000000012"),
            label="What shift was used?",
            description="Submit the numeric shift value as nexctf{N}.",
            index=1,
            points=75,
            malus=0,
            challenge_id=_cid("Caesar Cipher"),
        ),
        # OSINT Starter — 2 questions
        Question(
            id=UUID("b1000000-0000-4000-8000-000000000006"),
            label="Find the target's email",
            description="The target's GitHub profile holds the answer.",
            index=0,
            points=150,
            malus=0,
            challenge_id=_cid("OSINT Starter"),
        ),
        Question(
            id=UUID("b1000000-0000-4000-8000-000000000013"),
            label="Find the target's home city",
            description="Cross-reference their social media to find the city they live in.",
            index=1,
            points=200,
            malus=20,
            challenge_id=_cid("OSINT Starter"),
        ),
        # Misc Warmup — 1 question (challenge is inactive)
        Question(
            id=UUID("b1000000-0000-4000-8000-000000000007"),
            label="Read the description",
            description="The flag is in the challenge description.",
            index=0,
            points=50,
            malus=0,
            challenge_id=_cid("Misc Warmup"),
        ),
    ]


@fixtures.register(depends_on=["question"])
def hint() -> list[Hint]:
    def _qid(label: str) -> UUID:
        return fixtures.field("question", "label", label)

    return [
        Hint(
            id=UUID("c1000000-0000-4000-8000-000000000001"),
            title="Check the source",
            content="Right-click → View Page Source. Comments can hide secrets.",
            cost=15,
            order=0,
            question_id=_qid("Find the hidden flag"),
        ),
        Hint(
            id=UUID("c1000000-0000-4000-8000-000000000002"),
            title="Magic characters",
            content="What happens when you add a ' to the username field?",
            cost=20,
            order=0,
            question_id=_qid("Bypass the login"),
        ),
        Hint(
            id=UUID("c1000000-0000-4000-8000-000000000003"),
            title="UNION trick",
            content="UNION SELECT allows you to append results from another table.",
            cost=30,
            order=1,
            question_id=_qid("Bypass the login"),
        ),
        Hint(
            id=UUID("c1000000-0000-4000-8000-000000000007"),
            title="LOAD_FILE",
            content="MySQL's LOAD_FILE() function reads a file from the server filesystem.",
            cost=35,
            order=0,
            question_id=_qid("Read /etc/passwd"),
        ),
        Hint(
            id=UUID("c1000000-0000-4000-8000-000000000004"),
            title="strings command",
            content="Run `strings ./binary | grep nexctf` to find printable strings.",
            cost=25,
            order=0,
            question_id=_qid("Find the license key"),
        ),
        Hint(
            id=UUID("c1000000-0000-4000-8000-000000000006"),
            title="ltrace trick",
            content="ltrace intercepts library calls and can show strcmp arguments.",
            cost=25,
            order=0,
            question_id=_qid("What is the hardcoded salt?"),
        ),
        Hint(
            id=UUID("c1000000-0000-4000-8000-000000000005"),
            title="Shift amount",
            content="ROT13 is a Caesar cipher with shift 13. Try other shifts.",
            cost=10,
            order=0,
            question_id=_qid("Decrypt the message"),
        ),
    ]


@fixtures.register(depends_on=["question"])
def solution() -> list[MatchSolution]:
    def _qid(label: str) -> UUID:
        return fixtures.field("question", "label", label)

    return [
        MatchSolution(
            id=UUID("d1000000-0000-4000-8000-000000000001"),
            value="nexctf{web_basics_flag}",
            case_sensitive=False,
            question_id=_qid("Find the hidden flag"),
        ),
        MatchSolution(
            id=UUID("d1000000-0000-4000-8000-000000000008"),
            value="nexctf{basic_auth_bypass}",
            case_sensitive=False,
            question_id=_qid("Bypass the HTTP auth"),
        ),
        MatchSolution(
            id=UUID("d1000000-0000-4000-8000-000000000002"),
            value="nexctf{sql_injection_basic}",
            case_sensitive=False,
            question_id=_qid("Bypass the login"),
        ),
        MatchSolution(
            id=UUID("d1000000-0000-4000-8000-000000000003"),
            value="nexctf{admin_password_exposed}",
            case_sensitive=False,
            question_id=_qid("Extract the admin password"),
        ),
        MatchSolution(
            id=UUID("d1000000-0000-4000-8000-000000000009"),
            value="nexctf{etc_passwd_exposed}",
            case_sensitive=False,
            question_id=_qid("Read /etc/passwd"),
        ),
        MatchSolution(
            id=UUID("d1000000-0000-4000-8000-000000000004"),
            value="nexctf{license_r3v3rs3d}",
            case_sensitive=False,
            question_id=_qid("Find the license key"),
        ),
        MatchSolution(
            id=UUID("d1000000-0000-4000-8000-000000000010"),
            value="nexctf{s4lt_in_pl4in_sight}",
            case_sensitive=False,
            question_id=_qid("What is the hardcoded salt?"),
        ),
        MatchSolution(
            id=UUID("d1000000-0000-4000-8000-000000000011"),
            value="nexctf{ptrace_anti_debug}",
            case_sensitive=False,
            question_id=_qid("Patch the anti-debug check"),
        ),
        MatchSolution(
            id=UUID("d1000000-0000-4000-8000-000000000005"),
            value="nexctf{julius_w0uld_be_proud}",
            case_sensitive=False,
            question_id=_qid("Decrypt the message"),
        ),
        MatchSolution(
            id=UUID("d1000000-0000-4000-8000-000000000012"),
            value="nexctf{13}",
            case_sensitive=False,
            question_id=_qid("What shift was used?"),
        ),
        MatchSolution(
            id=UUID("d1000000-0000-4000-8000-000000000006"),
            value="target@example.com",
            case_sensitive=False,
            question_id=_qid("Find the target's email"),
        ),
        MatchSolution(
            id=UUID("d1000000-0000-4000-8000-000000000013"),
            value="nexctf{paris}",
            case_sensitive=False,
            question_id=_qid("Find the target's home city"),
        ),
        MatchSolution(
            id=UUID("d1000000-0000-4000-8000-000000000007"),
            value="nexctf{read_carefully}",
            case_sensitive=False,
            question_id=_qid("Read the description"),
        ),
    ]


@fixtures.register()
def team() -> list[Team]:
    return [
        Team(
            id=UUID("435127a0-f2fb-4d2b-87bd-91ab77328e71"),
            name="team1",
        ),
        Team(
            id=UUID("43512700-f2fb-4d2b-87bd-91ab77328e72"),
            name="team2",
        ),
        Team(
            id=UUID("43512700-f2fb-4d2b-87bd-91ab77328e73"),
            name="team3",
        ),
        Team(
            id=UUID("43512700-f2fb-4d2b-87bd-91ab77328e74"),
            name="team4",
        ),
    ]


@fixtures.register(depends_on=["team"])
def user() -> list[User]:
    def _tid(name: str) -> UUID:
        return fixtures.field("team", "name", name)

    users = [
        User(
            id=UUID("f9a973c4-aecb-4b20-8529-ff8c7ec103bd"),
            username="admin",
            email="admin@nexctf.lan",
            hashed_password="$argon2id$v=19$m=19456,t=2,p=1$AcmDj2+r/kwx+XoQvEoxNA$i7DQvA/gNP13qY7+lVYuAENAoePLLUtV2tstRpB2jos",  # "admin"
            role=UserRole.admin,
        ),
        User(
            id=UUID("c2d4e6f8-1a3b-4c5d-8e9f-0a1b2c3d4e5f"),
            username="moderator",
            email="moderator@nexctf.lan",
            hashed_password="$argon2id$v=19$m=19456,t=2,p=1$MEyLsujIFTvOwJsra1sJgg$O0ZofHlUIWVADJqpkmEjlp/rEv5S93AFCQnFcRwu6z8",  # "moderator"
            role=UserRole.moderator,
        ),
        User(
            id=UUID("1cd3b6dd-cd32-4984-aa25-fc2de4dd5544"),
            username="user1",
            email="user1@nexctf.lan",
            hashed_password="$argon2id$v=19$m=19456,t=2,p=1$KeTWinUnDbhWfx8v1wHK0w$nKdJGfiWLAsEaTYm+fEHDknZAA4yGarRMsudBfw1lII",  # "user1"
            team_id=_tid("team1"),
        ),
        User(
            id=UUID("83a86856-67d0-4603-9399-4bb58846944c"),
            username="user2",
            email="user2@nexctf.lan",
            hashed_password="$argon2id$v=19$m=19456,t=2,p=1$Qpo3ZMVBfpUD9ZJ/B9jWRQ$guz+AmQO8xHJ1fM3yMLr4rZDtREnkBCjREvEF40ccBg",  # "user2"
            team_id=_tid("team1"),
        ),
        User(
            id=UUID("f9a973c4-aecb-4b20-8529-ff8c7ec10301"),
            username="user3",
            email="user3@nexctf.lan",
            hashed_password="$argon2id$v=19$m=19456,t=2,p=1$KeTWinUnDbhWfx8v1wHK0w$nKdJGfiWLAsEaTYm+fEHDknZAA4yGarRMsudBfw1lII",  # "user1"
            team_id=_tid("team2"),
        ),
        User(
            id=UUID("f9a973c4-aecb-4b20-8529-ff8c7ec10302"),
            username="user4",
            email="user4@nexctf.lan",
            hashed_password="$argon2id$v=19$m=19456,t=2,p=1$KeTWinUnDbhWfx8v1wHK0w$nKdJGfiWLAsEaTYm+fEHDknZAA4yGarRMsudBfw1lII",  # "user1"
            team_id=_tid("team2"),
        ),
        User(
            id=UUID("f9a973c4-aecb-4b20-8529-ff8c7ec10303"),
            username="user5",
            email="user5@nexctf.lan",
            hashed_password="$argon2id$v=19$m=19456,t=2,p=1$KeTWinUnDbhWfx8v1wHK0w$nKdJGfiWLAsEaTYm+fEHDknZAA4yGarRMsudBfw1lII",  # "user1"
            team_id=_tid("team3"),
        ),
        User(
            id=UUID("f9a973c4-aecb-4b20-8529-ff8c7ec10304"),
            username="user6",
            email="user6@nexctf.lan",
            hashed_password="$argon2id$v=19$m=19456,t=2,p=1$KeTWinUnDbhWfx8v1wHK0w$nKdJGfiWLAsEaTYm+fEHDknZAA4yGarRMsudBfw1lII",  # "user1"
            team_id=_tid("team3"),
        ),
        User(
            id=UUID("f9a973c4-aecb-4b20-8529-ff8c7ec10305"),
            username="user7",
            email="user7@nexctf.lan",
            hashed_password="$argon2id$v=19$m=19456,t=2,p=1$KeTWinUnDbhWfx8v1wHK0w$nKdJGfiWLAsEaTYm+fEHDknZAA4yGarRMsudBfw1lII",  # "user1"
            team_id=_tid("team4"),
        ),
        User(
            id=UUID("f9a973c4-aecb-4b20-8529-ff8c7ec10306"),
            username="user8",
            email="user8@nexctf.lan",
            hashed_password="$argon2id$v=19$m=19456,t=2,p=1$KeTWinUnDbhWfx8v1wHK0w$nKdJGfiWLAsEaTYm+fEHDknZAA4yGarRMsudBfw1lII",  # "user1"
            team_id=_tid("team4"),
        ),
    ]
    # Seed users predate any verification flow; mark them verified so enabling
    # SMTP in dev does not lock them out (mirrors the migration backfill).
    for u in users:
        u.email_verified = True
    return users


@fixtures.register(depends_on=["user"])
def token() -> list[UserToken]:
    return [
        UserToken(
            id=UUID("26a7ec48-f11e-4795-8e96-a6ac95e5b410"),
            user_id=fixtures.field("user", "username", "admin"),
            token_hash="278e988e8437ac6c34fdcc9f43e43ed69d68361eb63808b97ae3befa3e989e0b",  # "nexctf_admin_token"
        )
    ]


@fixtures.register()
def tag() -> list[Tag]:
    return [
        Tag(
            id=UUID("95ace7e7-7afc-4bc3-b226-ab4f58649ec9"),
            name="Hard",
            description="",
            color="#e01b24",
        ),
        Tag(
            id=UUID("909d27a4-90d3-415c-b346-3b765d951701"),
            name="Medium",
            description="",
            color="#ff7800",
        ),
        Tag(
            id=UUID("bd970b07-2736-4b61-9b55-9a68a9d19a7d"),
            name="Easy",
            description="",
            color="#33d17a",
        ),
    ]


_TEAM1_ID = UUID("435127a0-f2fb-4d2b-87bd-91ab77328e71")
_TEAM2_ID = UUID("43512700-f2fb-4d2b-87bd-91ab77328e72")
_TEAM3_ID = UUID("43512700-f2fb-4d2b-87bd-91ab77328e73")
_TEAM4_ID = UUID("43512700-f2fb-4d2b-87bd-91ab77328e74")
_ADMIN_ID = UUID("f9a973c4-aecb-4b20-8529-ff8c7ec103bd")


@fixtures.register(depends_on=["team", "user", "question", "solution"])
def submission() -> list[Submission]:
    def _qid(label: str) -> UUID:
        return fixtures.field("question", "label", label)

    return [
        # ── team1 ─────────────────────────────────────────────────────────
        # Web Basics Q1: 1 wrong then correct
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000001"),
            answer="flag{wrong}",
            is_correct=False,
            points_earned=0,
            wrong_count_before=0,
            team_id=_TEAM1_ID,
            question_id=_qid("Find the hidden flag"),
            created_at=_t(70),
        ),
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000002"),
            answer="nexctf{web_basics_flag}",
            is_correct=True,
            points_earned=90,  # 100 - 1*10
            wrong_count_before=1,
            team_id=_TEAM1_ID,
            question_id=_qid("Find the hidden flag"),
            created_at=_t(75),
        ),
        # Web Basics Q2: first attempt
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000041"),
            answer="nexctf{basic_auth_bypass}",
            is_correct=True,
            points_earned=150,
            wrong_count_before=0,
            team_id=_TEAM1_ID,
            question_id=_qid("Bypass the HTTP auth"),
            created_at=_t(90),
        ),
        # SQL Q1: 2 wrong then correct
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000003"),
            answer="admin' OR '1'='1",
            is_correct=False,
            points_earned=0,
            wrong_count_before=0,
            team_id=_TEAM1_ID,
            question_id=_qid("Bypass the login"),
            created_at=_t(150),
        ),
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000004"),
            answer="' OR 1=1--",
            is_correct=False,
            points_earned=0,
            wrong_count_before=1,
            team_id=_TEAM1_ID,
            question_id=_qid("Bypass the login"),
            created_at=_t(162),
        ),
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000005"),
            answer="nexctf{sql_injection_basic}",
            is_correct=True,
            points_earned=120,  # 150 - 2*15
            wrong_count_before=2,
            team_id=_TEAM1_ID,
            question_id=_qid("Bypass the login"),
            created_at=_t(175),
        ),
        # Binary Reversing Q1: 1 wrong then correct
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000006"),
            answer="nexctf{wrong_key}",
            is_correct=False,
            points_earned=0,
            wrong_count_before=0,
            team_id=_TEAM1_ID,
            question_id=_qid("Find the license key"),
            created_at=_t(240),
        ),
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000007"),
            answer="nexctf{license_r3v3rs3d}",
            is_correct=True,
            points_earned=180,  # 200 - 1*20
            wrong_count_before=1,
            team_id=_TEAM1_ID,
            question_id=_qid("Find the license key"),
            created_at=_t(265),
        ),
        # Caesar Q1: 1 wrong then correct
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000008"),
            answer="nexctf{julius_would_be_proud}",
            is_correct=False,
            points_earned=0,
            wrong_count_before=0,
            team_id=_TEAM1_ID,
            question_id=_qid("Decrypt the message"),
            created_at=_t(180),
        ),
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000009"),
            answer="nexctf{julius_w0uld_be_proud}",
            is_correct=True,
            points_earned=90,  # 100 - 1*10
            wrong_count_before=1,
            team_id=_TEAM1_ID,
            question_id=_qid("Decrypt the message"),
            created_at=_t(195),
        ),
        # Caesar Q2: first attempt
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000042"),
            answer="nexctf{13}",
            is_correct=True,
            points_earned=75,
            wrong_count_before=0,
            team_id=_TEAM1_ID,
            question_id=_qid("What shift was used?"),
            created_at=_t(210),
        ),
        # ── team2 (top scorer — clean runs, fastest) ──────────────────────
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000011"),
            answer="nexctf{web_basics_flag}",
            is_correct=True,
            points_earned=100,
            wrong_count_before=0,
            team_id=_TEAM2_ID,
            question_id=_qid("Find the hidden flag"),
            created_at=_t(30),
        ),
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000051"),
            answer="nexctf{basic_auth_bypass}",
            is_correct=True,
            points_earned=150,
            wrong_count_before=0,
            team_id=_TEAM2_ID,
            question_id=_qid("Bypass the HTTP auth"),
            created_at=_t(45),
        ),
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000012"),
            answer="nexctf{sql_injection_basic}",
            is_correct=True,
            points_earned=150,
            wrong_count_before=0,
            team_id=_TEAM2_ID,
            question_id=_qid("Bypass the login"),
            created_at=_t(80),
        ),
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000013"),
            answer="nexctf{admin_password_exposed}",
            is_correct=True,
            points_earned=250,
            wrong_count_before=0,
            team_id=_TEAM2_ID,
            question_id=_qid("Extract the admin password"),
            created_at=_t(110),
        ),
        # SQL Q3: 1 wrong then correct
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000052"),
            answer="nexctf{wrong_file}",
            is_correct=False,
            points_earned=0,
            wrong_count_before=0,
            team_id=_TEAM2_ID,
            question_id=_qid("Read /etc/passwd"),
            created_at=_t(130),
        ),
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000053"),
            answer="nexctf{etc_passwd_exposed}",
            is_correct=True,
            points_earned=315,  # 350 - 1*35
            wrong_count_before=1,
            team_id=_TEAM2_ID,
            question_id=_qid("Read /etc/passwd"),
            created_at=_t(140),
        ),
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000014"),
            answer="nexctf{license_r3v3rs3d}",
            is_correct=True,
            points_earned=200,
            wrong_count_before=0,
            team_id=_TEAM2_ID,
            question_id=_qid("Find the license key"),
            created_at=_t(180),
        ),
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000054"),
            answer="nexctf{s4lt_in_pl4in_sight}",
            is_correct=True,
            points_earned=275,
            wrong_count_before=0,
            team_id=_TEAM2_ID,
            question_id=_qid("What is the hardcoded salt?"),
            created_at=_t(225),
        ),
        # Binary Q3: 2 wrong then correct
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000055"),
            answer="nexctf{bad_patch}",
            is_correct=False,
            points_earned=0,
            wrong_count_before=0,
            team_id=_TEAM2_ID,
            question_id=_qid("Patch the anti-debug check"),
            created_at=_t(250),
        ),
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000056"),
            answer="nexctf{another_wrong}",
            is_correct=False,
            points_earned=0,
            wrong_count_before=1,
            team_id=_TEAM2_ID,
            question_id=_qid("Patch the anti-debug check"),
            created_at=_t(260),
        ),
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000057"),
            answer="nexctf{ptrace_anti_debug}",
            is_correct=True,
            points_earned=320,  # 400 - 2*40
            wrong_count_before=2,
            team_id=_TEAM2_ID,
            question_id=_qid("Patch the anti-debug check"),
            created_at=_t(270),
        ),
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000015"),
            answer="nexctf{julius_w0uld_be_proud}",
            is_correct=True,
            points_earned=100,
            wrong_count_before=0,
            team_id=_TEAM2_ID,
            question_id=_qid("Decrypt the message"),
            created_at=_t(60),
        ),
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000058"),
            answer="nexctf{13}",
            is_correct=True,
            points_earned=75,
            wrong_count_before=0,
            team_id=_TEAM2_ID,
            question_id=_qid("What shift was used?"),
            created_at=_t(68),
        ),
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000016"),
            answer="target@example.com",
            is_correct=True,
            points_earned=150,
            wrong_count_before=0,
            team_id=_TEAM2_ID,
            question_id=_qid("Find the target's email"),
            created_at=_t(150),
        ),
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000059"),
            answer="nexctf{paris}",
            is_correct=True,
            points_earned=200,
            wrong_count_before=0,
            team_id=_TEAM2_ID,
            question_id=_qid("Find the target's home city"),
            created_at=_t(175),
        ),
        # ── team3 (slow, limited solves) ──────────────────────────────────
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000021"),
            answer="nexctf{web_basics_flag}",
            is_correct=True,
            points_earned=100,
            wrong_count_before=0,
            team_id=_TEAM3_ID,
            question_id=_qid("Find the hidden flag"),
            created_at=_t(240),
        ),
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000022"),
            answer="nexctf{julius_w0uld_be_proud}",
            is_correct=True,
            points_earned=100,
            wrong_count_before=0,
            team_id=_TEAM3_ID,
            question_id=_qid("Decrypt the message"),
            created_at=_t(330),
        ),
        # SQL Q1: wrong attempt, never solved
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000023"),
            answer="admin'--",
            is_correct=False,
            points_earned=0,
            wrong_count_before=0,
            team_id=_TEAM3_ID,
            question_id=_qid("Bypass the login"),
            created_at=_t(360),
        ),
        # ── team4 (minimal — OSINT only) ──────────────────────────────────
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000031"),
            answer="target@example.com",
            is_correct=True,
            points_earned=150,
            wrong_count_before=0,
            team_id=_TEAM4_ID,
            question_id=_qid("Find the target's email"),
            created_at=_t(210),
        ),
        # Web Basics Q1: wrong, never solved
        Submission(
            id=UUID("e1000000-0000-4000-8000-000000000032"),
            answer="nexctf{not_the_flag}",
            is_correct=False,
            points_earned=0,
            wrong_count_before=0,
            team_id=_TEAM4_ID,
            question_id=_qid("Find the hidden flag"),
            created_at=_t(300),
        ),
    ]


@fixtures.register(depends_on=["user", "hint"])
def hint_unlock() -> list[HintUnlock]:
    def _hid(title: str) -> UUID:
        return fixtures.field("hint", "title", title)

    return [
        HintUnlock(
            id=UUID("f1000000-0000-4000-8000-000000000001"),
            user_id=UUID("1cd3b6dd-cd32-4984-aa25-fc2de4dd5544"),  # user1
            hint_id=_hid("Magic characters"),
            cost_paid=20,
        ),
        HintUnlock(
            id=UUID("f1000000-0000-4000-8000-000000000002"),
            user_id=UUID("83a86856-67d0-4603-9399-4bb58846944c"),  # user2
            hint_id=_hid("strings command"),
            cost_paid=25,
        ),
        HintUnlock(
            id=UUID("f1000000-0000-4000-8000-000000000003"),
            user_id=UUID("f9a973c4-aecb-4b20-8529-ff8c7ec10303"),  # user5
            hint_id=_hid("Magic characters"),
            cost_paid=20,
        ),
        HintUnlock(
            id=UUID("f1000000-0000-4000-8000-000000000004"),
            user_id=UUID("f9a973c4-aecb-4b20-8529-ff8c7ec10303"),  # user5
            hint_id=_hid("Shift amount"),
            cost_paid=10,
        ),
    ]


@fixtures.register(depends_on=["team", "user"])
def score_adjustment() -> list[ScoreAdjustment]:
    return [
        ScoreAdjustment(
            id=UUID("f2000000-0000-4000-8000-000000000001"),
            amount=50,
            reason="Bonus for first blood on OSINT Starter",
            team_id=_TEAM4_ID,
            created_by_id=_ADMIN_ID,
        ),
        ScoreAdjustment(
            id=UUID("f2000000-0000-4000-8000-000000000002"),
            amount=-30,
            reason="Penalty for attempted cheating",
            team_id=_TEAM3_ID,
            created_by_id=_ADMIN_ID,
        ),
    ]
