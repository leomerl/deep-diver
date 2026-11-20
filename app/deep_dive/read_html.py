from minio import Minio

from app.storage import get_object


def read_html(client: Minio, bucket: str, key: str) -> str:
    return get_object(client, bucket, key).decode("utf-8")
