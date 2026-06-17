from fastapi_toolsets.crud import AsyncCrud
from sqlalchemy.orm import joinedload, selectinload

from nexctf.module.audit import AuditedCrud

from nexctf.model import (
    Challenge,
    ChallengeCategory,
    CustomFieldDefinition,
    CustomFieldValue,
    CustomPage,
    Event,
    File,
    Hint,
    Notification,
    OAuthAccount,
    OAuthProvider,
    OAuthServerClient,
    Question,
    SchedulerJob,
    SchedulerTask,
    ScoreAdjustment,
    Solution,
    Submission,
    Tag,
    Team,
    User,
    UserToken,
)


class TeamCrud(AsyncCrud[Team]):
    model = Team
    cursor_column = Team.created_at
    searchable_fields = [Team.name]
    facet_fields = []
    order_fields = [Team.name]
    default_load_options = [
        selectinload(Team.users),
        selectinload(Team.submissions),
        selectinload(Team.score_adjustments),
    ]


class CustomFieldDefinitionCrud(AuditedCrud[CustomFieldDefinition]):
    model = CustomFieldDefinition
    cursor_column = CustomFieldDefinition.created_at
    searchable_fields = [CustomFieldDefinition.name, CustomFieldDefinition.label]
    facet_fields = [CustomFieldDefinition.target, CustomFieldDefinition.field_type]
    order_fields = [
        CustomFieldDefinition.name,
        CustomFieldDefinition.target,
    ]
    default_load_options = []


class CustomFieldValueCrud(AsyncCrud[CustomFieldValue]):
    model = CustomFieldValue
    cursor_column = CustomFieldValue.created_at
    searchable_fields = []
    facet_fields = [CustomFieldValue.definition_id]
    order_fields = []
    default_load_options = [joinedload(CustomFieldValue.definition)]


class UserCrud(AsyncCrud[User]):
    model = User
    cursor_column = User.created_at
    searchable_fields = [User.username, User.email, User.role, (User.team, Team.name)]
    facet_fields = [User.is_active, User.role, (User.team, Team.name)]
    order_fields = [
        User.username,
        User.email,
        User.role,
        User.is_active,
        (User.team, Team.name),
    ]
    default_load_options = [joinedload(User.team)]


class UserTokenCrud(AsyncCrud[UserToken]):
    model = UserToken
    cursor_column = UserToken.created_at
    searchable_fields = [UserToken.name]
    facet_fields = []
    order_fields = [UserToken.name, (UserToken.user, User.username)]
    default_load_options = [joinedload(UserToken.user)]


class OAuthProviderCrud(AuditedCrud[OAuthProvider]):
    model = OAuthProvider
    cursor_column = OAuthProvider.created_at
    searchable_fields = [
        OAuthProvider.name,
        OAuthProvider.slug,
        OAuthProvider.discovery_url,
    ]
    facet_fields = [OAuthProvider.is_active]
    order_fields = [OAuthProvider.name, OAuthProvider.is_active]
    default_load_options = []


class OAuthAccountCrud(AsyncCrud[OAuthAccount]):
    model = OAuthAccount
    cursor_column = OAuthAccount.created_at
    searchable_fields = [
        OAuthAccount.subject,
        (OAuthAccount.user, User.username),
        (OAuthAccount.user, User.email),
    ]
    facet_fields = []
    order_fields = [
        OAuthAccount.subject,
        (OAuthAccount.user, User.username),
        (OAuthAccount.provider, OAuthProvider.name),
    ]
    default_load_options = [
        joinedload(OAuthAccount.user),
        joinedload(OAuthAccount.provider),
    ]


class ChallengeCrud(AuditedCrud[Challenge]):
    model = Challenge
    cursor_column = Challenge.created_at
    searchable_fields = [
        Challenge.title,
        Challenge.challenge_type,
        (Challenge.category, ChallengeCategory.name),
    ]
    facet_fields = [Challenge.challenge_type, Challenge.is_active, Challenge.sequential]
    order_fields = [
        Challenge.title,
        Challenge.challenge_type,
        Challenge.is_active,
        (Challenge.category, ChallengeCategory.name),
    ]
    default_load_options = [
        selectinload(Challenge.questions),
        selectinload(Challenge.tags),
        joinedload(Challenge.category),
    ]
    m2m_fields = {"tags_ids": Challenge.tags}


class ChallengeCategoryCrud(AuditedCrud[ChallengeCategory]):
    model = ChallengeCategory
    cursor_column = ChallengeCategory.created_at
    searchable_fields = [ChallengeCategory.name, ChallengeCategory.slug]
    facet_fields = []
    order_fields = [ChallengeCategory.name, ChallengeCategory.slug]
    default_load_options = [
        selectinload(ChallengeCategory.challenges),
    ]


class QuestionCrud(AuditedCrud[Question]):
    model = Question
    cursor_column = Question.created_at
    searchable_fields = [Question.label]
    facet_fields = [Question.challenge_id]
    order_fields = [
        Question.index,
        Question.points,
        Question.label,
        (Question.challenge, Challenge.title),
    ]
    default_load_options = [
        selectinload(Question.hints),
        selectinload(Question.solutions),
        selectinload(Question.files),
        selectinload(Question.tags),
        joinedload(Question.challenge),
    ]
    m2m_fields = {"files_ids": Question.files, "tags_ids": Question.tags}


class HintCrud(AuditedCrud[Hint]):
    model = Hint
    cursor_column = Hint.created_at
    searchable_fields = [Hint.title]
    facet_fields = [Hint.question_id]
    order_fields = [Hint.order, Hint.cost, Hint.title, (Hint.question, Question.label)]
    default_load_options = [selectinload(Hint.question)]


class SolutionCrud(AsyncCrud[Solution]):
    model = Solution
    cursor_column = Solution.created_at
    searchable_fields = [Solution.solve_type]
    facet_fields = [Solution.solve_type, Solution.question_id]
    order_fields = [Solution.solve_type, (Solution.question, Question.label)]
    default_load_options = [joinedload(Solution.question)]


class NotificationCrud(AuditedCrud[Notification]):
    model = Notification
    cursor_column = Notification.created_at
    searchable_fields = [Notification.title, Notification.content]
    facet_fields = [Notification.is_broadcast]
    order_fields = [
        Notification.title,
        Notification.is_broadcast,
        (Notification.created_by, User.username),
    ]
    default_load_options = [
        selectinload(Notification.teams),
        joinedload(Notification.created_by),
    ]
    m2m_fields = {"team_ids": Notification.teams}


class SubmissionCrud(AsyncCrud[Submission]):
    model = Submission
    cursor_column = Submission.created_at
    searchable_fields = [
        (Submission.question, Question.label),
    ]
    facet_fields = [
        Submission.is_correct,
        (Submission.team, Team.name),
    ]
    order_fields = [
        Submission.is_correct,
        Submission.points_earned,
        (Submission.team, Team.name),
        (Submission.question, Question.label),
    ]
    default_load_options = [
        joinedload(Submission.team),
        joinedload(Submission.question).joinedload(Question.challenge),
    ]


class FileCrud(AsyncCrud[File]):
    model = File
    cursor_column = File.created_at
    searchable_fields = [File.name, File.original_filename, File.mime_type]
    facet_fields = [File.mime_type]
    order_fields = [File.name, File.original_filename, File.file_size, File.mime_type]
    default_load_options = []


class ScoreAdjustmentCrud(AsyncCrud[ScoreAdjustment]):
    model = ScoreAdjustment
    cursor_column = ScoreAdjustment.created_at
    searchable_fields = [ScoreAdjustment.reason, (ScoreAdjustment.team, Team.name)]
    facet_fields = []
    order_fields = [
        ScoreAdjustment.amount,
        (ScoreAdjustment.team, Team.name),
        (ScoreAdjustment.challenge, Challenge.title),
        (ScoreAdjustment.created_by, User.username),
    ]
    default_load_options = [
        joinedload(ScoreAdjustment.team),
        joinedload(ScoreAdjustment.challenge),
        joinedload(ScoreAdjustment.created_by),
    ]


class TagCrud(AuditedCrud[Tag]):
    model = Tag
    cursor_column = Tag.created_at
    searchable_fields = [Tag.name, Tag.color]
    facet_fields = []
    order_fields = [Tag.name, Tag.color]
    default_load_options = []


class OAuthServerClientCrud(AuditedCrud[OAuthServerClient]):
    model = OAuthServerClient
    cursor_column = OAuthServerClient.created_at
    searchable_fields = [OAuthServerClient.name, OAuthServerClient.client_id]
    facet_fields = [OAuthServerClient.is_active]
    order_fields = [OAuthServerClient.name, OAuthServerClient.is_active]
    default_load_options = []


class SchedulerJobCrud(AsyncCrud[SchedulerJob]):
    model = SchedulerJob
    cursor_column = SchedulerJob.created_at
    searchable_fields = [SchedulerJob.name, SchedulerJob.job_type]
    facet_fields = [SchedulerJob.job_type, SchedulerJob.is_active]
    order_fields = [
        SchedulerJob.name,
        SchedulerJob.job_type,
        SchedulerJob.scheduled_at,
        SchedulerJob.is_active,
    ]
    default_load_options = [joinedload(SchedulerJob.created_by)]


class SchedulerTaskCrud(AsyncCrud[SchedulerTask]):
    model = SchedulerTask
    cursor_column = SchedulerTask.created_at
    searchable_fields = [SchedulerTask.status]
    facet_fields = [SchedulerTask.status]
    order_fields = [SchedulerTask.started_at, SchedulerTask.status]
    default_load_options = []


class PageCrud(AuditedCrud[CustomPage]):
    model = CustomPage
    cursor_column = CustomPage.created_at
    searchable_fields = [CustomPage.title, CustomPage.slug]
    facet_fields = [CustomPage.is_published, CustomPage.nav_placement]
    order_fields = [CustomPage.title, CustomPage.slug, CustomPage.is_published]
    default_load_options = []


class EventCrud(AsyncCrud[Event]):
    model = Event
    cursor_column = Event.created_at
    searchable_fields = [
        Event.event_type,
        Event.target_type,
        Event.target_label,
        (Event.actor, User.username),
    ]
    facet_fields = [
        Event.event_type,
        Event.target_type,
        (Event.actor, User.username),
    ]
    order_fields = [
        Event.event_type,
        Event.target_type,
        (Event.actor, User.username),
    ]
    default_load_options = [
        joinedload(Event.actor),
    ]
