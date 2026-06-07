"""Integration tests for nexctf.core.s3 (real S3-compatible backend)."""

import pytest
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointConnectionError

from nexctf.core import s3
from nexctf.core.config import settings
from nexctf.core.s3 import _safe_filename


def _s3_client_kwargs() -> dict:
    return dict(
        endpoint_url=settings.S3_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


@pytest.fixture(scope="module", autouse=True)
def ensure_s3_bucket():
    """Create the test bucket once per module if it does not already exist.

    Skips the entire module when S3 is not reachable so tests show as SKIPPED
    rather than cascading ERRORs that hide the real cause.
    """
    import boto3

    client = boto3.client("s3", **_s3_client_kwargs())
    try:
        client.create_bucket(Bucket=settings.S3_BUCKET)
    except EndpointConnectionError:
        pytest.skip(f"S3 not reachable at {settings.S3_URL}")
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code not in ("BucketAlreadyExists", "BucketAlreadyOwnedByYou"):
            raise
    finally:
        client.close()


@pytest.fixture(autouse=True)
async def _cleanup(s3_key):
    """Delete the per-test S3 object after each test, ignoring failures."""
    yield
    try:
        await s3.delete(s3_key)
    except Exception:
        pass


async def test_upload_object_is_reachable_via_presigned_url(s3_key):
    await s3.upload(s3_key, b"hello world", "text/plain")
    url = await s3.presigned_view_url(s3_key)
    assert s3_key in url


async def test_upload_without_content_type(s3_key):
    await s3.upload(s3_key, b"raw bytes")
    url = await s3.presigned_view_url(s3_key)
    assert s3_key in url


async def test_delete_succeeds_after_upload(s3_key):
    await s3.upload(s3_key, b"temporary", "application/octet-stream")
    # Should not raise
    await s3.delete(s3_key)


async def test_presigned_download_url_contains_key(s3_key):
    await s3.upload(s3_key, b"data", "application/octet-stream")
    url = await s3.presigned_download_url(s3_key, "report.pdf")

    assert s3_key in url
    assert "response-content-disposition" in url.lower()


async def test_presigned_download_url_contains_filename(s3_key):
    await s3.upload(s3_key, b"data", "application/octet-stream")
    url = await s3.presigned_download_url(s3_key, "my report.pdf")

    assert "my" in url


async def test_presigned_download_url_uses_presign_endpoint(s3_key):
    await s3.upload(s3_key, b"data", "text/plain")
    url = await s3.presigned_download_url(s3_key, "f.txt")

    assert url.startswith(settings.S3_PRESIGN_URL)


async def test_presigned_download_url_custom_expiry(s3_key):
    await s3.upload(s3_key, b"data", "text/plain")
    url = await s3.presigned_download_url(s3_key, "f.txt", expires=300)

    assert "300" in url


async def test_presigned_view_url_contains_key(s3_key):
    await s3.upload(s3_key, b"data", "image/png")
    url = await s3.presigned_view_url(s3_key)

    assert s3_key in url


async def test_presigned_view_url_omits_content_disposition(s3_key):
    await s3.upload(s3_key, b"data", "image/png")
    url = await s3.presigned_view_url(s3_key)

    assert "response-content-disposition" not in url.lower()


async def test_presigned_view_url_uses_presign_endpoint(s3_key):
    await s3.upload(s3_key, b"data", "text/plain")
    url = await s3.presigned_view_url(s3_key)

    assert url.startswith(settings.S3_PRESIGN_URL)


async def test_presigned_view_url_with_filename_adds_content_disposition(s3_key):
    await s3.upload(s3_key, b"data", "image/png")
    url = await s3.presigned_view_url(s3_key, filename="photo.png")

    assert "response-content-disposition" in url.lower()


async def test_presigned_view_url_with_filename_uses_inline_disposition(s3_key):
    await s3.upload(s3_key, b"data", "image/png")
    url = await s3.presigned_view_url(s3_key, filename="photo.png")

    assert "inline" in url


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("report.pdf", "report.pdf"),
        ('file"name.pdf', 'file\\"name.pdf'),
        ("file\\name.pdf", "file\\\\name.pdf"),
        ("file\rname.pdf", "filename.pdf"),
        ("file\nname.pdf", "filename.pdf"),
        ("file\r\nname.pdf", "filename.pdf"),
        # header injection: CRLF stripped, quote escaped — result is safe flat string
        ('evil";\r\nX-Injected: yes\r\n\r\n.pdf', 'evil\\";X-Injected: yes.pdf'),
        # backslash then quote: both escaped independently (order matters)
        ('back\\slash"quote', 'back\\\\slash\\"quote'),
    ],
)
def test_safe_filename(filename: str, expected: str) -> None:
    assert _safe_filename(filename) == expected
