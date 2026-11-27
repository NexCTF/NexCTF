"""Size checks and hashing for uploaded files."""

import asyncio
import hashlib
from typing import BinaryIO

from fastapi import UploadFile

from nexctf.core.config import settings
from nexctf.exceptions import UploadTooLargeError

_CHUNK = 1024 * 1024


def checked_size(upload: UploadFile) -> int:
    """The upload's size in bytes, refusing one over ``MAX_UPLOAD_BYTES``."""
    size = upload.size or 0
    if size > settings.MAX_UPLOAD_BYTES:
        raise UploadTooLargeError()
    return size


def _digest(fileobj: BinaryIO) -> str:
    digest = hashlib.sha256()
    fileobj.seek(0)
    while chunk := fileobj.read(_CHUNK):
        digest.update(chunk)
    fileobj.seek(0)
    return digest.hexdigest()


async def sha256_of(upload: UploadFile) -> str:
    """Hex SHA-256 of the upload's content, leaving it rewound."""
    return await asyncio.to_thread(_digest, upload.file)
