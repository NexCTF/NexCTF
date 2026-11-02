"""Annotated string types shared by the API schemas and the bundle format."""

from typing import Annotated

from pydantic import Field

Slug = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$", max_length=64)]
LinkUrl = Annotated[
    str, Field(pattern=r"^(?i:https?://|mailto:)[^\s]+$", max_length=2048)
]
