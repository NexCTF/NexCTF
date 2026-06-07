import logging
import logging.config
import os
from contextlib import asynccontextmanager

import nexctf.settings as _  # noqa: F401 — register config definitions
from nexctf.api.openapi import setup_docs
from nexctf.api.routes import router
from nexctf.core.appconfig import load_from_db
from nexctf.core.config import settings
from nexctf.core.db import get_db_context
from nexctf.core.cache import get_client as get_redis_client
from nexctf.plugins import init_plugins
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_toolsets.exceptions import init_exceptions_handlers

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
        await load_from_db(session, get_redis_client())
        await init_plugins(app, session)
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.all_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
init_exceptions_handlers(app=app)

v1_router = APIRouter(prefix=settings.API_V1_STR)
v1_router.include_router(router=router)
app.include_router(v1_router)

setup_docs(app, _ADMIN_PREFIX)
