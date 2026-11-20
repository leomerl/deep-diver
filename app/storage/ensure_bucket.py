from minio import Minio


def ensure_bucket(client: Minio, bucket: str) -> None:
    """Create `bucket` if it doesn't exist. Two workers racing to create it is harmless: one wins, both see it."""
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
