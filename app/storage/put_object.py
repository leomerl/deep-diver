from io import BytesIO

from minio import Minio


def put_object(client: Minio, bucket: str, key: str, data: bytes, content_type: str) -> None:
    """Write `data` under `key`, replacing any object already there."""
    client.put_object(bucket, key, BytesIO(data), len(data), content_type=content_type)
