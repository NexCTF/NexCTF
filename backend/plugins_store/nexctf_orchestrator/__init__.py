from pathlib import Path

from nexctf.core.appconfig import ConfigDef, ConfigType
from nexctf.plugins import (
    challenge_registry,
    frontend_registry,
    register_plugin_configs,
    route_registry,
)

from .api import router
from .model import OrchestratorChallenge
from .schema import (
    AdminOrchestratorChallengeCreate,
    AdminOrchestratorChallengeRead,
    AdminOrchestratorChallengeUpdate,
)

register_plugin_configs(
    "Orchestrator",
    ConfigDef(
        key="instance_url",
        label="Orchestrator instance URL",
        default="http://localhost:9000",
        description="Base URL of the NexCTF orchestrator API instance.",
        type=ConfigType.URL,
    ),
    ConfigDef(
        key="instance_token",
        label="Orchestrator instance token",
        default="",
        description="Bearer token used to authenticate API calls to the orchestrator.",
        type=ConfigType.STRING,
    ),
    ConfigDef(
        key="instance_verify",
        label="Verify SSL/TLS certificates",
        default=True,
        description="Whether to verify SSL/TLS certificates when connecting to the orchestrator.",
    ),
    icon="box",
)

frontend_registry.register(
    key="nexctf_orchestrator",
    dist_dir=Path(__file__).parent / "frontend" / "dist",
    slots=["challenge_panel"],
    challenge_types=["orchestrator"],
)

challenge_registry.register(
    type_name="orchestrator",
    model=OrchestratorChallenge,
    create_schema=AdminOrchestratorChallengeCreate,
    update_schema=AdminOrchestratorChallengeUpdate,
    read_schema=AdminOrchestratorChallengeRead,
)

route_registry.register(
    router=router,
    prefix="/orchestrator",
    scope="public",
    tags=["Orchestrator"],
)
