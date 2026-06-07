import io
from contextlib import asynccontextmanager

import aioboto3
from botocore.config import Config

from nexctf.core.config import settings

_session = aioboto3.Session()
_config = Config(signature_version="s3v4", s3={"addressing_style": "path"})


def _client_kwargs(endpoint_url: str) -> dict:
    return dict(
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        config=_config,
    )


@asynccontextmanager
async def _client():
    async with _session.client("s3", **_client_kwargs(settings.S3_URL)) as client:
        yield client


@asynccontextmanager
async def _public_client():
    """Client whose endpoint is embedded in presigned URLs — must be browser-accessible."""
    async with _session.client(
        "s3", **_client_kwargs(settings.S3_PRESIGN_URL)
    ) as client:
        yield client


async def upload(key: str, data: bytes, content_type: str | None = None) -> None:
    extra = {"ContentType": content_type} if content_type else {}
    async with _client() as client:
        await client.upload_fileobj(
            io.BytesIO(data), settings.S3_BUCKET, key, ExtraArgs=extra
        )


async def delete(key: str) -> None:
    async with _client() as client:
        await client.delete_object(Bucket=settings.S3_BUCKET, Key=key)


def _safe_filename(filename: str) -> str:
    """Escape double-quotes and strip CRLF for safe Content-Disposition embedding."""
    return (
        filename.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "")
        .replace("\n", "")
    )


async def presigned_download_url(key: str, filename: str, expires: int = 3600) -> str:
    """Presigned URL with Content-Disposition: attachment — triggers browser download."""
    async with _public_client() as client:
        return await client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.S3_BUCKET,
                "Key": key,
                "ResponseContentDisposition": f'attachment; filename="{_safe_filename(filename)}"',
            },
            ExpiresIn=expires,
        )


async def presigned_view_url(
    key: str, filename: str | None = None, expires: int = 3600
) -> str:
    """Presigned URL with inline Content-Disposition — browser renders based on Content-Type."""
    params: dict = {"Bucket": settings.S3_BUCKET, "Key": key}
    if filename:
        params["ResponseContentDisposition"] = (
            f'inline; filename="{_safe_filename(filename)}"'
        )
    async with _public_client() as client:
        return await client.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=expires,
        )
