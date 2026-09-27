from fastapi_toolsets.db import Database

from nexctf.core.config import settings

db = Database(
    str(settings.SQLALCHEMY_DATABASE_URI),
    pool_size=settings.POSTGRES_POOL_SIZE,
    max_overflow=settings.POSTGRES_MAX_OVERFLOW,
    pool_timeout=settings.POSTGRES_POOL_TIMEOUT,
    pool_pre_ping=True,
)

# Pool for the auth validators' sessions, separate from the request sessions'.
auth_db = Database(
    str(settings.SQLALCHEMY_DATABASE_URI),
    pool_size=settings.POSTGRES_AUTH_POOL_SIZE,
    max_overflow=settings.POSTGRES_AUTH_MAX_OVERFLOW,
    pool_timeout=settings.POSTGRES_POOL_TIMEOUT,
    pool_pre_ping=True,
)

# Session context manager for code outside request handlers (CLI, worker,
# background tasks). Also referenced by [tool.fastapi-toolsets] db_context.
get_db_context = db.session
get_auth_db_context = auth_db.session
