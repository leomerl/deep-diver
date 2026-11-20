import hashlib

from minio import Minio

from app.storage import put_object

HTML_CONTENT_TYPE = "text/html; charset=utf-8"


def store_html(client: Minio, bucket: str, html: str) -> str:
    """Upload the page under the hash of its bytes and return the key.

    Content-addressed: a retried job that renders the same page writes the same key, so retries can't pile up
    copies, and a key never points at different content.
    """
    data = html.encode("utf-8")
    key = f"{hashlib.sha256(data).hexdigest()}.html"
    put_object(client, bucket, key, data, HTML_CONTENT_TYPE)
    return key
