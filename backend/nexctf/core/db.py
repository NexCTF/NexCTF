from fastapi_toolsets.db import create_db_context, create_db_dependency
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from nexctf.core.config import settings

engine = create_async_engine(str(settings.SQLALCHEMY_DATABASE_URI), future=True)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

get_db = create_db_dependency(session_maker=async_session_maker)
get_db_context = create_db_context(session_maker=async_session_maker)
