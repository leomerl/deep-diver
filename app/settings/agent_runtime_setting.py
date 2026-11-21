from redis import Redis

from app.agent import AgentRuntime

# Shared by the API (writes) and every worker (reads per agent), like the agent slots; a missing key means gateway.
AGENT_RUNTIME_KEY = "settings:agent_runtime"


def get_agent_runtime(client: Redis) -> AgentRuntime:
    value = client.get(AGENT_RUNTIME_KEY)
    return AgentRuntime.gateway if value is None else AgentRuntime(str(value))


def set_agent_runtime(client: Redis, runtime: AgentRuntime) -> None:
    client.set(AGENT_RUNTIME_KEY, runtime.value)
