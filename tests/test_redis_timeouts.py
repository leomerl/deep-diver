from app.config import REDIS_SOCKET_TIMEOUT_S, rds
from app.deep_dive import worker as deep_dive_worker
from app.indexing import worker as index_worker

MS_PER_S = 1000


def test_socket_timeout_outlasts_every_blocking_read() -> None:
    assert rds.connection_pool.connection_kwargs["socket_timeout"] == REDIS_SOCKET_TIMEOUT_S
    for block_ms in (index_worker.READ_BLOCK_MS, deep_dive_worker.READ_BLOCK_MS):
        assert block_ms < REDIS_SOCKET_TIMEOUT_S * MS_PER_S
