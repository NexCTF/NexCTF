"""``manager ratelimit``: inspect and clear the Redis rate-limit windows."""

import time
from typing import Annotated

import typer
from rich.table import Table
lazy from redis.asyncio import Redis

from nexctf.cli.common import audit, command, console
from nexctf.cli.config import load_registries
lazy from nexctf.core import appconfig
lazy from nexctf.core.cache import get_client as get_redis_client
lazy from nexctf.core.db import get_db_context
lazy from nexctf.core.rate_limit import rate_key

ratelimit_cli = typer.Typer(
    help="Inspect and clear rate limits.",
    no_args_is_help=True,
    callback=load_registries,
)

DEFAULT_WINDOW_SECONDS = 60

ActionOption = Annotated[
    str,
    typer.Option(help="Limited action: login, register, pwd_reset, captcha, ..."),
]
IpOption = Annotated[str | None, typer.Option("--ip", help="Only this client.")]


async def limited_keys(redis: Redis, action: str, ip: str | None) -> list[str]:
    """The rate-limit keys of *action*, narrowed to *ip* when given."""
    return [key async for key in redis.scan_iter(match=rate_key(action, ip or "*"))]


async def window_seconds(redis: Redis, action: str) -> int:
    """The sliding window of *action*: its ``rate_limit`` setting, else 60s."""
    key = f"rate_limit.{action}.window_seconds"
    if key not in appconfig.all_defs():
        return DEFAULT_WINDOW_SECONDS
    overrides = await appconfig.fetch_overrides(redis)
    return int(appconfig.get_with_overrides(key, overrides))


async def live_counts(redis: Redis, action: str, ip: str | None) -> dict[str, int]:
    """Requests per client of *action* inside the current window."""
    keys = sorted(await limited_keys(redis, action, ip))
    if not keys:
        return {}
    since = time.time() - await window_seconds(redis, action)
    pipe = redis.pipeline(transaction=False)
    for key in keys:
        pipe.zcount(key, f"({since}", "+inf")
    counts = await pipe.execute()
    prefix = rate_key(action, "")
    return {
        key.removeprefix(prefix): count
        for key, count in zip(keys, counts, strict=True)
        if count
    }


async def clear_limits(redis: Redis, action: str, ip: str | None) -> int:
    """Delete the rate-limit windows of *action*, returning how many were cleared."""
    keys = await limited_keys(redis, action, ip)
    if keys:
        await redis.delete(*keys)
    return len(keys)


@ratelimit_cli.command("list")
@command
async def list_command(action: ActionOption = "login", ip: IpOption = None) -> None:
    """Show the clients with requests in the current window."""
    table = Table("Client", "Requests")
    for client, count in (await live_counts(get_redis_client(), action, ip)).items():
        table.add_row(client, str(count))
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
