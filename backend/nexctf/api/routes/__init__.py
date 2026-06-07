from fastapi import APIRouter

from .admin import admin_router
from .auth import auth_router
from .challenge import challenge_router
from .file import file_router
from .info import info_router
from .me import me_router
from .notification import notification_router
from .oauth_server import oauth_router
from .page import page_router
from .plugin import plugin_router
from .scoreboard import scoreboard_router
from .sse import sse_router

router = APIRouter(prefix="")


router.include_router(router=admin_router)
router.include_router(router=auth_router)
router.include_router(router=challenge_router)
router.include_router(router=file_router)
router.include_router(router=info_router)
router.include_router(router=me_router)
router.include_router(router=notification_router)
router.include_router(router=page_router)
router.include_router(router=plugin_router)
router.include_router(router=scoreboard_router)
router.include_router(router=sse_router)
router.include_router(router=oauth_router)
