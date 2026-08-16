import logging
import logging.config
import os
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi_multiauth.exceptions import UnauthorizedError as MultiAuthUnauthorizedError
from fastapi_toolsets.exceptions import UnauthorizedError, init_exceptions_handlers
from fastapi_toolsets.schemas import ErrorResponse

# Imported for its side effect: registers the config definitions.
import nexctf.settings as _  # noqa: F401
from nexctf.api.openapi import setup_docs
from nexctf.api.routes import router
from nexctf.core.appconfig import sync_to_redis
from nexctf.core.cache import get_client as get_redis_client
from nexctf.core.config import settings
from nexctf.core.db import db, get_db_context
from nexctf.exceptions import OAuth2ProtocolError
from nexctf.plugins import init_plugins

_ADMIN_PREFIX = f"{settings.API_V1_STR}/admin"

logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(levelprefix)s %(message)s",
                "use_colors": None,
            },
            "app": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(levelprefix)s %(name)s \u2014 %(message)s",
                "use_colors": None,
            },
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stderr",
            },
            "app": {
                "class": "logging.StreamHandler",
                "formatter": "app",
                "stream": "ext://sys.stderr",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
            "app": {"handlers": ["app"], "level": "INFO", "propagate": False},
        },
    }
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.environ.get("NEXCTF_TEST_MODE"):
        yield
        return

    async with get_db_context() as session:
        await sync_to_redis(session, get_redis_client())
        await init_plugins(app, session)
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
db.install(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.all_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
init_exceptions_handlers(app=app)


@app.exception_handler(MultiAuthUnauthorizedError)
async def multiauth_unauthorized_handler(
    request: Request, exc: MultiAuthUnauthorizedError
) -> JSONResponse:
    """Render fastapi-multiauth's "no credentials" 401 as the toolsets AUTH-401 body.

    The auth sources raise this when a request carries no credential at all.
    Map it to the same structured response a validator-raised UnauthorizedError
    produces so the API error contract stays consistent, while preserving the
    RFC 7235 ``WWW-Authenticate`` challenge the source attached.
    """
    api_error = UnauthorizedError.api_error
    return JSONResponse(
        status_code=api_error.code,
        content=ErrorResponse(
            data=api_error.data,
            message=api_error.msg,
            description=api_error.desc,
            error_code=api_error.err_code,
        ).model_dump(),
        headers=exc.headers,
    )


@app.exception_handler(OAuth2ProtocolError)
async def oauth2_protocol_error_handler(
    request: Request, exc: OAuth2ProtocolError
) -> JSONResponse:
    """Render OAuth2 wire-protocol errors in the RFC body shape.

    Third-party OAuth clients read ``error`` per RFC 6749 §5.2, not the app's
    ``ErrorResponse``. Registered explicitly so it wins over the toolsets
    ``HTTPException`` handler, which Starlette would otherwise resolve to.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.error, "error_description": exc.error_description},
        headers=exc.headers,
    )


v1_router = APIRouter(prefix=settings.API_V1_STR)
v1_router.include_router(router=router)
app.include_router(v1_router)

setup_docs(app, _ADMIN_PREFIX)
