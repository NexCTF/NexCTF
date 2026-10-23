from fastapi_toolsets.schemas import PydanticBase

from nexctf.schema.user import AccountCreate


class SetupStatusRead(PydanticBase):
    admin_required: bool


class SetupAdminCreate(AccountCreate):
    token: str
