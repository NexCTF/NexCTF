"""Central config definitions.

Labels and descriptions are i18n keys — the frontend resolves them.
Add new settings here.
"""

from nexctf.core.appconfig import ConfigDef, ConfigRegistry, ConfigType

config = ConfigRegistry()


@config.category("competition", "config.category.competition", icon="trophy")
def _competition():
    return [
        ConfigDef(
            key="ctf.name",
            label="config.ctf.name.label",
            default="NexCTF",
            description="config.ctf.name.description",
            type=ConfigType.STRING,
        ),
        ConfigDef(
            key="ctf.description",
            label="config.ctf.description.label",
            default="",
            description="config.ctf.description.description",
            type=ConfigType.TEXT,
        ),
        ConfigDef(
            key="ctf.start_time",
            label="config.ctf.start_time.label",
            default="",
            description="config.ctf.start_time.description",
            type=ConfigType.DATETIME,
        ),
        ConfigDef(
            key="ctf.end_time",
            label="config.ctf.end_time.label",
            default="",
            description="config.ctf.end_time.description",
            type=ConfigType.DATETIME,
        ),
        ConfigDef(
            key="ctf.freeze_time",
            label="config.ctf.freeze_time.label",
            default="",
            description="config.ctf.freeze_time.description",
            type=ConfigType.DATETIME,
        ),
        ConfigDef(
            key="ctf.hide_challenges_before_start",
            label="config.ctf.hide_challenges_before_start.label",
            default=True,
            description="config.ctf.hide_challenges_before_start.description",
        ),
        ConfigDef(
            key="ctf.team_size",
            label="config.ctf.team_size.label",
            default=4,
            description="config.ctf.team_size.description",
        ),
        ConfigDef(
            key="ctf.allow_registration",
            label="config.ctf.allow_registration.label",
            default=True,
            description="config.ctf.allow_registration.description",
        ),
        ConfigDef(
            key="ctf.allow_team_creation",
            label="config.ctf.allow_team_creation.label",
            default=True,
            description="config.ctf.allow_team_creation.description",
        ),
        ConfigDef(
            key="ctf.release_writeups_after_end",
            label="config.ctf.release_writeups_after_end.label",
            default=False,
            description="config.ctf.release_writeups_after_end.description",
        ),
    ]


@config.category("security", "config.category.security", icon="shield")
def _security():
    return [
        ConfigDef(
            key="rate_limit.submit.enabled",
            label="config.rate_limit.submit.enabled.label",
            default=True,
            description="config.rate_limit.submit.enabled.description",
        ),
        ConfigDef(
            key="rate_limit.submit.max_requests",
            label="config.rate_limit.submit.max_requests.label",
            default=10,
            description="config.rate_limit.submit.max_requests.description",
        ),
        ConfigDef(
            key="rate_limit.submit.window_seconds",
            label="config.rate_limit.submit.window_seconds.label",
            default=60,
            description="config.rate_limit.submit.window_seconds.description",
        ),
        ConfigDef(
            key="rate_limit.login.enabled",
            label="config.rate_limit.login.enabled.label",
            default=True,
            description="config.rate_limit.login.enabled.description",
        ),
        ConfigDef(
            key="rate_limit.login.max_requests",
            label="config.rate_limit.login.max_requests.label",
            default=10,
            description="config.rate_limit.login.max_requests.description",
        ),
        ConfigDef(
            key="rate_limit.login.window_seconds",
            label="config.rate_limit.login.window_seconds.label",
            default=60,
            description="config.rate_limit.login.window_seconds.description",
        ),
        ConfigDef(
            key="captcha.enabled",
            label="config.captcha.enabled.label",
            default=False,
            description="config.captcha.enabled.description",
        ),
        ConfigDef(
            key="captcha.cap_api_url",
            label="config.captcha.cap_api_url.label",
            default="",
            description="config.captcha.cap_api_url.description",
            type=ConfigType.URL,
        ),
        ConfigDef(
            key="captcha.cap_site_key",
            label="config.captcha.cap_site_key.label",
            default="",
            description="config.captcha.cap_site_key.description",
            type=ConfigType.STRING,
        ),
        ConfigDef(
            key="captcha.cap_secret_key",
            label="config.captcha.cap_secret_key.label",
            default="",
            description="config.captcha.cap_secret_key.description",
            type=ConfigType.STRING,
        ),
    ]


@config.category("email", "config.category.email", icon="mail")
def _email():
    return [
        ConfigDef(
            key="email.enabled",
            label="config.email.enabled.label",
            default=False,
            description="config.email.enabled.description",
        ),
        ConfigDef(
            key="email.smtp_host",
            label="config.email.smtp_host.label",
            default="",
            description="config.email.smtp_host.description",
            type=ConfigType.STRING,
        ),
        ConfigDef(
            key="email.smtp_port",
            label="config.email.smtp_port.label",
            default=587,
            description="config.email.smtp_port.description",
        ),
        ConfigDef(
            key="email.smtp_username",
            label="config.email.smtp_username.label",
            default="",
            description="config.email.smtp_username.description",
            type=ConfigType.STRING,
        ),
        ConfigDef(
            key="email.smtp_password",
            label="config.email.smtp_password.label",
            default="",
            description="config.email.smtp_password.description",
            type=ConfigType.STRING,
        ),
        ConfigDef(
            key="email.security",
            label="config.email.security.label",
            default="starttls",
            description="config.email.security.description",
            type=ConfigType.CHOICE,
            choices=["none", "starttls", "tls"],
        ),
        ConfigDef(
            key="email.from_address",
            label="config.email.from_address.label",
            default="",
            description="config.email.from_address.description",
            type=ConfigType.STRING,
        ),
        ConfigDef(
            key="email.from_name",
            label="config.email.from_name.label",
            default="",
            description="config.email.from_name.description",
            type=ConfigType.STRING,
        ),
    ]


@config.category("visibility", "config.category.visibility", icon="eye")
def _visibility():
    return [
        ConfigDef(
            key="visibility.scoreboard",
            label="config.visibility.scoreboard.label",
            default="public",
            description="config.visibility.scoreboard.description",
            type=ConfigType.CHOICE,
            choices=["public", "authenticated", "hidden"],
        ),
        ConfigDef(
            key="visibility.challenges",
            label="config.visibility.challenges.label",
            default="authenticated",
            description="config.visibility.challenges.description",
            type=ConfigType.CHOICE,
            choices=["public", "authenticated", "hidden"],
        ),
    ]


@config.category("appearance", "config.category.appearance", icon="palette")
def _appearance():
    return [
        ConfigDef(
            key="appearance.logo_url",
            label="config.appearance.logo_url.label",
            default="",
            description="config.appearance.logo_url.description",
            type=ConfigType.URL,
        ),
        ConfigDef(
            key="appearance.primary_color",
            label="config.appearance.primary_color.label",
            default="",
            description="config.appearance.primary_color.description",
            type=ConfigType.COLOR,
        ),
        ConfigDef(
            key="appearance.favicon_url",
            label="config.appearance.favicon_url.label",
            default="",
            description="config.appearance.favicon_url.description",
            type=ConfigType.URL,
        ),
    ]
