from fastapi_toolsets.schemas import PydanticBase
from pydantic import EmailStr


class AdminEmailTestRequest(PydanticBase):
    to: EmailStr
