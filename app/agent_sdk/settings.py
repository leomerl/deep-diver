from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentSdkSettings:
    model: str
    # Extra environment for the Claude Code binary. Empty: it uses the Claude Code login of the host it runs on.
    # For API-key billing a caller passes ANTHROPIC_API_KEY (and ANTHROPIC_BASE_URL, CLAUDE_CONFIG_DIR as needed).
    env: Mapping[str, str] = field(default_factory=dict)
