from fastapi import APIRouter, HTTPException, status
from redis.exceptions import RedisError

from app.config import rds
from app.settings import AppSettings, get_agent_runtime, set_agent_runtime

router = APIRouter(prefix="/settings", tags=["settings"])
STORE_DOWN = "settings store unavailable, retry"


@router.get("")
def get_settings() -> AppSettings:
    try:
        return AppSettings(agent_runtime=get_agent_runtime(rds))
    except RedisError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, STORE_DOWN) from e


@router.put("")
def put_settings(settings: AppSettings) -> AppSettings:
    """Workers read the setting when each agent starts, so the change applies to the next agent, not the next restart."""
    try:
        set_agent_runtime(rds, settings.agent_runtime)
    except RedisError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, STORE_DOWN) from e
    return settings
