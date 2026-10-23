from fastapi import APIRouter, Depends

from nexctf.api.dep import require_setup_done

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
from .setup import setup_router
from .sse import sse_router
from .team import team_router

router = APIRouter(prefix="")
gated_router = APIRouter(dependencies=[Depends(require_setup_done)])


gated_router.include_router(router=admin_router)
gated_router.include_router(router=auth_router)
gated_router.include_router(router=challenge_router)
gated_router.include_router(router=file_router)
gated_router.include_router(router=info_router)
gated_router.include_router(router=me_router)
gated_router.include_router(router=notification_router)
gated_router.include_router(router=page_router)
gated_router.include_router(router=plugin_router)
gated_router.include_router(router=scoreboard_router)
gated_router.include_router(router=sse_router)
gated_router.include_router(router=team_router)
gated_router.include_router(router=oauth_router)
router.include_router(router=gated_router)
router.include_router(router=setup_router)
