from botocore.exceptions import BotoCoreError, ClientError


class ObjectStorageError(Exception):
    pass


class ObjectStorage:
    def __init__(self, client, bucket: str):
        self._client = client
        self._bucket = bucket

    def upload(self, key: str, content: bytes) -> None:
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=content,
                ContentType="application/pdf",
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
