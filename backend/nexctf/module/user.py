"""User account writes shared by the admin API and the ``manager`` CLI."""

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf import crud
from nexctf.model import User
from nexctf.module.audit import audit_actor
from nexctf.module.events import emit
from nexctf.schema.user import UserTotpUpdate


async def reset_totp(session: AsyncSession, redis: Redis, user: User) -> None:
    """Clear *user*'s TOTP secret and record it in the audit log."""
    await crud.UserCrud.update(
        session=session,
        filters=[User.id == user.id],
        obj=UserTotpUpdate(id=user.id, totp_secret=None),
    )
    actor_id, ip = audit_actor()
    await emit(
        session,
        redis,
        event_type="admin.user_totp_reset",
        actor_id=actor_id,
        ip=ip,
        meta={"target_user_id": str(user.id), "target_username": user.username},
    )
