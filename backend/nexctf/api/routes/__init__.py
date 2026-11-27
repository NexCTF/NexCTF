from fastapi import APIRouter, Depends

from nexctf.api.dep import require_setup_done

from .admin import admin_router
from .auth import auth_router
from .challenge import challenge_router
from .file import file_router
from .info import info_router, public_info_router
from .me import me_router
from .notification import notification_router
from .oauth_server import oauth_router
from .page import page_router
from .plugin import plugin_router
from .scoreboard import scoreboard_router
from .setup import setup_router
from .sse import sse_router
from .team import team_router

router = APIRouter(prefix="")
gated_router = APIRouter(dependencies=[Depends(require_setup_done)])


for gated in (
    admin_router,
    auth_router,
    challenge_router,
    file_router,
    info_router,
    me_router,
    notification_router,
    page_router,
    plugin_router,
    scoreboard_router,
    sse_router,
    team_router,
    oauth_router,
):
    gated_router.include_router(router=gated)
router.include_router(router=gated_router)
router.include_router(router=public_info_router)
router.include_router(router=setup_router)
