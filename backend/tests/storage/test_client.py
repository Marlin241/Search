import pytest
from botocore.exceptions import ClientError

from app.storage.client import ObjectStorage, ObjectStorageError


class FakeBotoClient:
    """Minimal stand-in for a boto3 S3 client's put/get/delete_object methods."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.fail_next = False

    def put_object(self, Bucket, Key, Body, ContentType):
        if self.fail_next:
            raise ClientError({"Error": {"Code": "500", "Message": "boom"}}, "PutObject")
        self.objects[Key] = Body

    def get_object(self, Bucket, Key):
        if self.fail_next:
            raise ClientError({"Error": {"Code": "500", "Message": "boom"}}, "GetObject")
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey", "Message": "not found"}}, "GetObject")

        class _Body:
            def read(self_inner) -> bytes:
                return self.objects[Key]

        return {"Body": _Body()}

    def delete_object(self, Bucket, Key):
        if self.fail_next:
            raise ClientError({"Error": {"Code": "500", "Message": "boom"}}, "DeleteObject")
        self.objects.pop(Key, None)


def test_upload_then_download_roundtrips_bytes():
    client = FakeBotoClient()
    storage = ObjectStorage(client, "bucket")

    storage.upload("key.pdf", b"%PDF-1.4 fake content")

    assert storage.download("key.pdf") == b"%PDF-1.4 fake content"


def test_upload_wraps_client_error():
    client = FakeBotoClient()
    client.fail_next = True
    storage = ObjectStorage(client, "bucket")

    with pytest.raises(ObjectStorageError):
        storage.upload("key.pdf", b"data")


def test_download_wraps_client_error_on_missing_key():
    client = FakeBotoClient()
    storage = ObjectStorage(client, "bucket")

    with pytest.raises(ObjectStorageError):
        storage.download("missing.pdf")


def test_delete_removes_object():
    client = FakeBotoClient()
    storage = ObjectStorage(client, "bucket")
    storage.upload("key.pdf", b"data")

    storage.delete("key.pdf")

    with pytest.raises(ObjectStorageError):
        storage.download("key.pdf")
