"""``manager ratelimit``: inspect and clear the Redis rate-limit windows."""

from typing import Annotated

import typer
from rich.table import Table
lazy from redis.asyncio import Redis

from nexctf.cli.common import audit, command, console
lazy from nexctf.core.cache import get_client as get_redis_client
lazy from nexctf.core.db import get_db_context
lazy from nexctf.core.rate_limit import rate_key

ratelimit_cli = typer.Typer(help="Inspect and clear rate limits.", no_args_is_help=True)

ActionOption = Annotated[
    str,
    typer.Option(help="Limited action: login, register, pwd_reset, captcha, ..."),
]
IpOption = Annotated[str | None, typer.Option("--ip", help="Only this client address.")]


async def limited_keys(redis: Redis, action: str, ip: str | None) -> list[str]:
    """The rate-limit keys of *action*, narrowed to *ip* when given."""
    return [key async for key in redis.scan_iter(match=rate_key(action, ip or "*"))]


async def clear_limits(redis: Redis, action: str, ip: str | None) -> int:
    """Delete the rate-limit windows of *action*, returning how many were cleared."""
    keys = await limited_keys(redis, action, ip)
    if keys:
        await redis.delete(*keys)
    return len(keys)


@ratelimit_cli.command("list")
@command
async def list_command(action: ActionOption = "login", ip: IpOption = None) -> None:
    """Show the addresses with requests in the current window."""
    redis = get_redis_client()
    keys = sorted(await limited_keys(redis, action, ip))
    pipe = redis.pipeline(transaction=False)
    for key in keys:
        pipe.zcard(key)
    counts = await pipe.execute() if keys else []
    table = Table("Address", "Requests")
    prefix = rate_key(action, "")
    for key, count in zip(keys, counts, strict=True):
        table.add_row(key.removeprefix(prefix), str(count))
    console.print(table)


@ratelimit_cli.command("clear")
@command
async def clear_command(action: ActionOption = "login", ip: IpOption = None) -> None:
    """Reset the rate-limit windows, for every address or only --ip."""
    redis = get_redis_client()
    cleared = await clear_limits(redis, action, ip)
    async with get_db_context() as session:
        await audit(
            session, redis, "admin.rate_limit_cleared", action=action, ip=ip or "*"
        )
    console.print(f"Cleared {cleared} {action} rate-limit window(s).")
