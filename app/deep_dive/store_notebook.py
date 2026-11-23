import hashlib

from minio import Minio

from app.models import NotebookBase
from app.storage import put_object

JSON_CONTENT_TYPE = "application/json"


def store_notebook(client: Minio, bucket: str, notebook: NotebookBase) -> str:
    """Upload the notebook as JSON under the hash of its bytes and return the key; content-addressed like the page."""
    data = notebook.model_dump_json().encode("utf-8")
    key = f"{hashlib.sha256(data).hexdigest()}.json"
    put_object(client, bucket, key, data, JSON_CONTENT_TYPE)
    return key
