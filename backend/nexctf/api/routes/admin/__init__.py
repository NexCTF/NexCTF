from fastapi import APIRouter, Security

from nexctf.api.security import auth
from nexctf.model import UserRole

from .category import category_router
from .challenge import challenge_router
from .config import config_router
from .custom_field import custom_field_router, custom_field_value_router
from .event import event_router
from .file import file_router
from .hint import hint_router
from .notification import notification_router
from .oauth import oauth_router
from .oauth_client import oauth_client_router
from .page import page_router as admin_page_router
from .plugin import plugin_router
from .question import question_router
from .scheduler import scheduler_router
from .score_adjustment import score_adjustment_router
from .scoreboard import scoreboard_router
from .solution import solution_router
from .stats import stats_router
from .submission import submission_router
from .tag import tag_router
from .team import team_router
from .user import user_router

admin_router = APIRouter(
    prefix="/admin", dependencies=[Security(auth.require(role=UserRole.admin))]
)

admin_router.include_router(router=category_router)
admin_router.include_router(router=challenge_router)
admin_router.include_router(router=config_router)
admin_router.include_router(router=custom_field_router)
admin_router.include_router(router=custom_field_value_router)
admin_router.include_router(router=event_router)
admin_router.include_router(router=file_router)
admin_router.include_router(router=hint_router)
admin_router.include_router(router=notification_router)
admin_router.include_router(router=oauth_router)
admin_router.include_router(router=oauth_client_router)
admin_router.include_router(router=plugin_router)
admin_router.include_router(router=question_router)
admin_router.include_router(router=scheduler_router)
admin_router.include_router(router=score_adjustment_router)
admin_router.include_router(router=scoreboard_router)
admin_router.include_router(router=stats_router)
admin_router.include_router(router=solution_router)
admin_router.include_router(router=submission_router)
admin_router.include_router(router=admin_page_router)
admin_router.include_router(router=tag_router)
admin_router.include_router(router=team_router)
admin_router.include_router(router=user_router)
