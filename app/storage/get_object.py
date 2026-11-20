from minio import Minio


def get_object(client: Minio, bucket: str, key: str) -> bytes:
    """The object's bytes. Raises minio.error.S3Error (code NoSuchKey) if it doesn't exist."""
    response = client.get_object(bucket, key)
    try:
        return response.read()
    finally:
        # minio hands back a pooled urllib3 response: release it, or the pool runs dry.
        response.close()
        response.release_conn()
