"""Rendering of API errors as the toolsets error body."""

from collections.abc import Mapping

from fastapi.responses import JSONResponse
from fastapi_toolsets.schemas import ApiError, ErrorResponse


def api_error_response(
    api_error: ApiError, headers: Mapping[str, str] | None = None
) -> JSONResponse:
    """Render *api_error* as the toolsets error body, keeping *headers*."""
    return JSONResponse(
        status_code=api_error.code,
        content=ErrorResponse(
            data=api_error.data,
            message=api_error.msg,
            description=api_error.desc,
            error_code=api_error.err_code,
        ).model_dump(),
        headers=headers,
    )
