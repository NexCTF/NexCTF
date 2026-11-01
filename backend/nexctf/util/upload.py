"""Size checks for uploaded files."""

from fastapi import UploadFile

from nexctf.core.config import settings
from nexctf.exceptions import UploadTooLargeError


def checked_size(upload: UploadFile) -> int:
    """The upload's size in bytes, refusing one over ``MAX_UPLOAD_BYTES``."""
    size = upload.size or 0
    if size > settings.MAX_UPLOAD_BYTES:
        raise UploadTooLargeError()
    return size
