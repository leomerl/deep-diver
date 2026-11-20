import uuid
from collections.abc import Iterator

import pytest
import urllib3
from minio import Minio
from minio.error import S3Error

from app.storage import ensure_bucket, get_object, put_object

# Same defaults as docker-compose's minio service.
ENDPOINT, ACCESS_KEY, SECRET_KEY = "localhost:9000", "dd-minio", "dd-minio-secret"


@pytest.fixture
def bucket() -> Iterator[tuple[Minio, str]]:
    # No retries and a short timeout, so a stopped minio skips in seconds instead of a minute.
    http = urllib3.PoolManager(timeout=urllib3.Timeout(connect=2, read=5), retries=False)
    client = Minio(ENDPOINT, ACCESS_KEY, SECRET_KEY, secure=False, http_client=http)
    name = f"test-{uuid.uuid4().hex[:12]}"
    try:
        ensure_bucket(client, name)
    except urllib3.exceptions.HTTPError:  # connection refused or timed out
        pytest.skip("minio is not running: docker compose up -d minio")
    yield client, name
    for obj in client.list_objects(name, recursive=True):
        client.remove_object(name, obj.object_name or "")
    client.remove_bucket(name)


def test_put_then_get_round_trips_and_ensure_is_idempotent(bucket: tuple[Minio, str]) -> None:
    client, name = bucket
    ensure_bucket(client, name)
    put_object(client, name, "a/b.html", b"<p>hi</p>", "text/html")

    assert get_object(client, name, "a/b.html") == b"<p>hi</p>"


def test_missing_key_raises(bucket: tuple[Minio, str]) -> None:
    client, name = bucket
    with pytest.raises(S3Error) as e:
        get_object(client, name, "missing.html")
    assert e.value.code == "NoSuchKey"
