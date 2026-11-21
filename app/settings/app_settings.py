from pydantic import BaseModel

from app.agent import AgentRuntime


class AppSettings(BaseModel):
    """The dashboard's settings: one shape for the GET response and the PUT body, so they can't drift."""

    agent_runtime: AgentRuntime
