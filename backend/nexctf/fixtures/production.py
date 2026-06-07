"""Production-only fixtures — seeded once on first deploy."""

from uuid import UUID

from fastapi_toolsets.fixtures import FixtureRegistry
from fastapi_toolsets.fixtures.enum import Context

from nexctf.model.page import CustomPage

fixtures = FixtureRegistry(contexts=[Context.PRODUCTION])


@fixtures.register()
def default_pages() -> list[CustomPage]:
    return [
        CustomPage(
            id=UUID("10000000-0000-4000-8000-000000000001"),
            slug="home",
            title="Home",
            content=(
                "# Welcome to {{event_name}}\n\n"
                "Edit this page from the admin panel to customise the home page.\n\n"
                "The event starts in: **{{countdown_to_start}}**"
            ),
            is_published=True,
        )
    ]
