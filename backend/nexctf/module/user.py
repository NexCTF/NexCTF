"""User account writes shared by the admin API and the ``manager`` CLI."""

from fastapi_toolsets.exceptions import ConflictError
from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf import crud
from nexctf.api.security import hash_password
from nexctf.model import User
from nexctf.module.audit import audit_actor
from nexctf.module.events import emit
from nexctf.schema.user import AdminUserCreate, UserCreate, UserTotpUpdate


async def _audit_user(
    session: AsyncSession, redis: Redis, event_type: str, user: User
) -> None:
    """Record *event_type* on *user* with the bound actor and IP."""
    actor_id, ip = audit_actor()
    await emit(
        session,
        redis,
        event_type=event_type,
        actor_id=actor_id,
        ip=ip,
        meta={"target_user_id": str(user.id), "target_username": user.username},
    )


async def create_verified_user(
    session: AsyncSession, redis: Redis, obj: AdminUserCreate
) -> User:
    """Create a user with a verified email and record it in the audit log."""
    try:
        user = await crud.UserCrud.create(
            session=session,
            obj=UserCreate(
                username=obj.username,
                email=obj.email,
                hashed_password=hash_password(obj.password),
                email_verified=True,
                role=obj.role,
                team_id=obj.team_id,
            ),
        )
    except IntegrityError as exc:
        raise ConflictError(detail="Username or email already taken") from exc
    await _audit_user(session, redis, "admin.user_created", user)
    return user


async def reset_totp(session: AsyncSession, redis: Redis, user: User) -> None:
    """Clear *user*'s TOTP secret and record it in the audit log."""
    await crud.UserCrud.update(
        session=session,
        filters=[User.id == user.id],
        obj=UserTotpUpdate(id=user.id, totp_secret=None),
    )
    await _audit_user(session, redis, "admin.user_totp_reset", user)
