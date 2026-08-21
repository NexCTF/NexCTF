"""Helpers for the development fixtures."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from nexctf.core.config import settings
from nexctf.model import ConfigEntry

logger = logging.getLogger(__name__)

SITE_NAME = "nexctf-dev"
CAP_TIMEOUT = httpx.Timeout(10.0, connect=2.0)


def cap_api_url() -> str:
    """CAP's public URL, as the browser must be able to reach it."""
    return os.environ.get("CAP_PUBLIC_URL", "http://localhost:3000").rstrip("/")


def admin_headers(client: httpx.Client, admin_key: str) -> dict[str, str]:
    """Log in and build the bearer header CAP's admin API expects."""
    login = client.post("/auth/login", json={"admin_key": admin_key})
    login.raise_for_status()
    body = login.json()
    session = base64.b64encode(
        json.dumps(
            {"token": body["session_token"], "hash": body["hashed_token"]}
        ).encode()
    ).decode()
    return {"Authorization": f"Bearer {session}"}


def provision_cap_site() -> tuple[str, str] | None:
    """Create the dev CAP site and return (site_key, secret), or None when CAP is down."""
    admin_key = os.environ.get("CAP_ADMIN_KEY")
    if not admin_key:
        return None

    url = cap_api_url()
    try:
        with httpx.Client(base_url=url, timeout=CAP_TIMEOUT) as client:
            headers = admin_headers(client, admin_key)

            existing = client.get("/server/keys", headers=headers)
            existing.raise_for_status()
            for key in existing.json():
                if key.get("name") == SITE_NAME:
                    client.delete(f"/server/keys/{key['siteKey']}", headers=headers)

            created = client.post(
                "/server/keys", headers=headers, json={"name": SITE_NAME}
            )
            created.raise_for_status()
            site = created.json()
    except httpx.HTTPError, KeyError:
        logger.warning("could not provision the dev CAP site at %s", url)
        return None

    return site["siteKey"], site["secretKey"]


def stored_config_keys() -> set[str]:
    """Config keys already in the database, which fixtures must not overwrite."""

    async def fetch() -> set[str]:
        engine = create_async_engine(str(settings.SQLALCHEMY_DATABASE_URI))
        try:
            async with engine.connect() as conn:
                return set((await conn.execute(select(ConfigEntry.key))).scalars())
        finally:
            await engine.dispose()

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(fetch())).result()
