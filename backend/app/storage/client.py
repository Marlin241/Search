from botocore.exceptions import BotoCoreError, ClientError


class ObjectStorageError(Exception):
    pass


class ObjectStorage:
    def __init__(self, client, bucket: str):
        self._client = client
        self._bucket = bucket

    def upload(
        self, key: str, content: bytes, content_type: str = "application/pdf"
    ) -> None:
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
            )
        except (BotoCoreError, ClientError) as exc:
            raise ObjectStorageError(f"Échec de l'upload de l'objet '{key}'.") from exc

    def download(self, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return response["Body"].read()
        except (BotoCoreError, ClientError) as exc:
            raise ObjectStorageError(
                f"Échec du téléchargement de l'objet '{key}'."
            ) from exc

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except (BotoCoreError, ClientError) as exc:
            raise ObjectStorageError(
                f"Échec de la suppression de l'objet '{key}'."
            ) from exc

    def delete_prefix(self, prefix: str) -> int:
        """Delete every object whose key starts with `prefix`. Returns the
        number deleted. Used to purge a user's objects on account deletion."""
        deleted = 0
        token: str | None = None
        try:
            while True:
                kwargs: dict = {"Bucket": self._bucket, "Prefix": prefix}
                if token is not None:
                    kwargs["ContinuationToken"] = token
                page = self._client.list_objects_v2(**kwargs)
                for obj in page.get("Contents", []):
                    self._client.delete_object(Bucket=self._bucket, Key=obj["Key"])
                    deleted += 1
                if not page.get("IsTruncated"):
                    break
                token = page.get("NextContinuationToken")
        except (BotoCoreError, ClientError) as exc:
            raise ObjectStorageError(
                f"Échec de la suppression du préfixe '{prefix}'."
            ) from exc
        return deleted
