from enum import StrEnum


class AgentRuntime(StrEnum):
    gateway = "gateway"  # our loop (run_agent) on the in-house gateway; the API key pays
    agent_sdk = "agent_sdk"  # the Claude Agent SDK's loop; on a host, the user's Claude Code login pays
