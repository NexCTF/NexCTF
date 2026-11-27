"""Schemas of the first-run setup endpoints."""

from fastapi_toolsets.schemas import PydanticBase

from nexctf.schema.user import AccountCreate


class SetupStatusRead(PydanticBase):
    """Whether the instance still waits for its first admin."""

    admin_required: bool


class SetupAdminCreate(AccountCreate):
    """The first admin's account, with the console setup token."""

    token: str
