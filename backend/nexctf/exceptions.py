"""Domain-specific API exceptions for NexCTF."""

from fastapi_toolsets.exceptions import ApiException
from fastapi_toolsets.schemas import ApiError


class AuthError(ApiException, abstract=True):
    """Base for authentication and registration errors."""


class InvalidCredentialsError(AuthError):
    api_error = ApiError(
        code=401,
        msg="Invalid credentials",
        desc="The username or password is incorrect.",
        err_code="AUTH-401",
    )


class AccountDisabledError(AuthError):
    api_error = ApiError(
        code=403,
        msg="Account disabled",
        desc="Your account has been disabled. Contact an administrator.",
        err_code="AUTH-403-DISABLED",
    )


class RegistrationDisabledError(AuthError):
    api_error = ApiError(
        code=403,
        msg="Registration disabled",
        desc="New user registration is currently disabled.",
        err_code="AUTH-403-REG-DISABLED",
    )


class InvalidResetTokenError(AuthError):
    api_error = ApiError(
        code=400,
        msg="Invalid reset token",
        desc="The password reset token is invalid or has expired.",
        err_code="AUTH-400-RESET-TOKEN",
    )


class TotpError(ApiException, abstract=True):
    """Base for TOTP / two-factor authentication errors."""


class TotpRequiredError(TotpError):
    api_error = ApiError(
        code=403,
        msg="Two-factor authentication required",
        desc="Please enter your TOTP code to continue.",
        err_code="AUTH-TOTP-REQUIRED",
    )


class InvalidOtpError(TotpError):
    api_error = ApiError(
        code=401,
        msg="Invalid OTP code",
        desc="The one-time password is incorrect or has expired.",
        err_code="AUTH-401-OTP",
    )


class TotpAlreadyEnabledError(TotpError):
    api_error = ApiError(
        code=409,
        msg="TOTP already enabled",
        desc="Two-factor authentication is already active on this account.",
        err_code="TOTP-409-ENABLED",
    )


class TotpNotEnabledError(TotpError):
    api_error = ApiError(
        code=409,
        msg="TOTP not enabled",
        desc="Two-factor authentication is not active on this account.",
        err_code="TOTP-409-DISABLED",
    )


class TeamError(ApiException, abstract=True):
    """Base for team membership and management errors."""


class NoTeamError(TeamError):
    api_error = ApiError(
        code=403,
        msg="Team required",
        desc="You must be in a team to submit answers.",
        err_code="SUB-403-TEAM",
    )


class TeamCreationDisabledError(TeamError):
    api_error = ApiError(
        code=403,
        msg="Team creation disabled",
        desc="Creating or joining teams is currently disabled.",
        err_code="TEAM-403-DISABLED",
    )


class AlreadyInTeamError(TeamError):
    api_error = ApiError(
        code=409,
        msg="Already in a team",
        desc="You are already a member of a team.",
        err_code="TEAM-409-MEMBER",
    )


class NotInTeamError(TeamError):
    api_error = ApiError(
        code=409,
        msg="Not in a team",
        desc="You are not currently in a team.",
        err_code="TEAM-409-NOT-MEMBER",
    )


class TeamFullError(TeamError):
    api_error = ApiError(
        code=409,
        msg="Team is full",
        desc="This team has reached its maximum member count.",
        err_code="TEAM-409-FULL",
    )


class InvalidInviteCodeError(TeamError):
    api_error = ApiError(
        code=404,
        msg="Invalid invite code",
        desc="No team found with this invite code.",
        err_code="TEAM-404-CODE",
    )


class CaptchaError(ApiException, abstract=True):
    """Base for captcha verification errors."""


class CaptchaRequiredError(CaptchaError):
    api_error = ApiError(
        code=400,
        msg="Captcha required",
        desc="Please complete the captcha challenge.",
        err_code="AUTH-CAPTCHA-REQUIRED",
    )


class CaptchaInvalidError(CaptchaError):
    api_error = ApiError(
        code=400,
        msg="Captcha verification failed",
        desc="The captcha token is invalid or has expired. Please try again.",
        err_code="AUTH-CAPTCHA-INVALID",
    )


class CaptchaMisconfiguredError(CaptchaError):
    api_error = ApiError(
        code=500,
        msg="Captcha misconfigured",
        desc="The captcha service is not properly configured. Contact an administrator.",
        err_code="CAPTCHA-500",
    )


class OAuthError(ApiException, abstract=True):
    """Base for OAuth provider and account linking errors."""


class OAuthAccountAlreadyLinkedError(OAuthError):
    api_error = ApiError(
        code=409,
        msg="OAuth account already linked",
        desc="This provider account is already linked to a different user.",
        err_code="OAUTH-409-ALREADY-LINKED",
    )


class CannotUnlinkLastOAuthError(OAuthError):
    api_error = ApiError(
        code=409,
        msg="Cannot unlink last OAuth account",
        desc="You have no password set — keep at least one linked provider to retain login access.",
        err_code="OAUTH-409-LAST",
    )


class OAuthProviderConfigError(OAuthError):
    api_error = ApiError(
        code=500,
        msg="OAuth provider misconfigured",
        desc="The provider has no userinfo URL configured.",
        err_code="OAUTH-500",
    )


class OAuthProviderResponseError(OAuthError):
    api_error = ApiError(
        code=502,
        msg="OAuth provider error",
        desc="The provider returned an invalid response.",
        err_code="OAUTH-502",
    )


class EventNotStartedError(ApiException):
    api_error = ApiError(
        code=403,
        msg="CTF not started",
        desc="The CTF has not started yet.",
        err_code="CTF-403-NOT-STARTED",
    )


class EventEndedError(ApiException):
    api_error = ApiError(
        code=403,
        msg="CTF ended",
        desc="The CTF has ended. Submissions are no longer accepted.",
        err_code="CTF-403-ENDED",
    )


class SequentialChallengeError(ApiException):
    api_error = ApiError(
        code=403,
        msg="Previous question not solved",
        desc="Complete the previous question first.",
        err_code="SUB-403-SEQ",
    )


class ConfigValidationError(ApiException):
    api_error = ApiError(
        code=422,
        msg="Configuration validation failed",
        desc="One or more configuration values are invalid.",
        err_code="CFG-422",
    )

    def __init__(self, errors: list[str]) -> None:
        super().__init__(desc="; ".join(errors))


class NothingToUpdateError(ApiException):
    api_error = ApiError(
        code=422,
        msg="Nothing to update",
        desc="Provide at least one field to update.",
        err_code="FILE-422",
    )


class FileNotFoundApiError(ApiException):
    api_error = ApiError(
        code=404,
        msg="File not found",
        desc="No file exists with the given identifier.",
        err_code="FILE-404",
    )


class InternalServerError(ApiException):
    api_error = ApiError(
        code=500,
        msg="Internal server error",
        desc="An unexpected error occurred.",
        err_code="INTERNAL-500",
    )
