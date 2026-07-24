from __future__ import annotations

import asyncio
from typing import Protocol

import boto3
from botocore.client import BaseClient


class ObjectStore(Protocol):
    async def put(self, *, checksum: str, media_type: str, body: bytes) -> str: ...


class S3ObjectStore:
    def __init__(
        self,
        *,
        bucket: str,
        access_key: str,
        secret_key: str,
        endpoint_url: str | None,
    ) -> None:
        self._bucket = bucket
        self._client: BaseClient = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    async def put(self, *, checksum: str, media_type: str, body: bytes) -> str:
        key = f"artifacts/sha256/{checksum[:2]}/{checksum}"
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=body,
            ContentType=media_type,
            Metadata={"sha256": checksum},
        )
        return key
